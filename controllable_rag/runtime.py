"""Runtime budget orchestration and independent callback-based usage audit."""

from threading import Lock

from langchain_community.callbacks import get_openai_callback

from .budget import BudgetLedger, ModelBudgetExceeded, activate_budget
from .config import get_settings
from .tracing import persist_trace


class ConcurrentThreadExecutionError(RuntimeError):
    """Fail fast when one in-process Agent receives overlapping thread writes."""

    def __init__(self, thread_id):
        self.diagnostics = {
            "status": "rejected",
            "error_type": type(self).__name__,
            "thread_id_present": bool(thread_id),
        }
        super().__init__("The checkpoint thread already has an active execution")


def _positive_budget(name, value):
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero, got {parsed}")
    return parsed


def stop_for_runtime_budget(
    state, reason, usage, diagnostics=None, budget_enforcement=None
):
    messages = {
        "model_request_budget_exhausted": (
            "Unable to continue within the configured model-request budget."
        ),
        "token_budget_exhausted": "Unable to continue within the configured token budget.",
        "execution_deadline_exhausted": (
            "Unable to continue within the configured execution deadline."
        ),
        "embedding_request_budget_exhausted": (
            "Unable to continue within the configured embedding-request budget."
        ),
        "embedding_input_budget_exhausted": (
            "Unable to continue within the configured embedding-input budget."
        ),
    }
    trace_events = list(state.get("trace_events") or [])
    trace_events.append(
        {
            "sequence": len(trace_events) + 1,
            "node": "runtime_budget_exhausted",
            "duration_ms": 0.0,
            "status": "budget_exhausted",
            "step_count": state.get("step_count", 0),
            "tool": state.get("tool", ""),
            "budget_enforcement": (
                budget_enforcement
                or ("pre_request" if diagnostics else "node_boundary_fallback")
            ),
        }
    )
    return {
        **state,
        "curr_state": "budget_exhausted",
        "response": messages[reason],
        "termination_reason": reason,
        "model_requests": usage.successful_requests,
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "token_accounting_available": (diagnostics or {}).get(
            "budget_accounting_complete",
            state.get("token_accounting_available", False),
        ),
        "budget_mode": "hard_preflight_with_boundary_fallback",
        "budget_diagnostics": diagnostics or {},
        "elapsed_seconds": (diagnostics or {}).get(
            "elapsed_seconds", state.get("elapsed_seconds", 0.0)
        ),
        "embedding_requests": (diagnostics or {}).get(
            "embedding_requests", state.get("embedding_requests", 0)
        ),
        "embedding_inputs": (diagnostics or {}).get(
            "embedding_inputs", state.get("embedding_inputs", 0)
        ),
        "trace_events": trace_events,
    }


def _persist_if_enabled(state, settings):
    if not state.get("trace_enabled", False):
        return state
    try:
        path = persist_trace(state, settings.effective_trace_directory)
    except Exception as error:
        # Trace storage must not replace a valid answer/control result. Persist only
        # a safe error type in state and let operators alert on this flag.
        return {
            **state,
            "trace_persisted": False,
            "trace_path": "",
            "trace_persistence_error": type(error).__name__,
        }
    return {
        **state,
        "trace_persisted": True,
        "trace_path": str(path),
        "trace_persistence_error": "",
    }


class BoundedAgent:
    """Enforce factory-created chat requests before dispatch, with usage fallback."""

    def __init__(self, compiled_graph):
        self.compiled_graph = compiled_graph
        self._active_thread_ids = set()
        self._active_thread_ids_lock = Lock()

    @staticmethod
    def _checkpoint_thread_id(config):
        if not isinstance(config, dict):
            return None
        configurable = config.get("configurable")
        if not isinstance(configurable, dict):
            return None
        thread_id = configurable.get("thread_id")
        return str(thread_id) if thread_id is not None else None

    def _claim_thread(self, thread_id):
        if thread_id is None:
            return
        with self._active_thread_ids_lock:
            if thread_id in self._active_thread_ids:
                raise ConcurrentThreadExecutionError(thread_id)
            self._active_thread_ids.add(thread_id)

    def _release_thread(self, thread_id):
        if thread_id is None:
            return
        with self._active_thread_ids_lock:
            self._active_thread_ids.discard(thread_id)

    def _limits(self, inputs):
        settings = get_settings()
        return (
            _positive_budget(
                "max_model_requests",
                inputs.get("max_model_requests", settings.agent_max_model_requests),
            ),
            _positive_budget(
                "max_total_tokens",
                inputs.get("max_total_tokens", settings.agent_max_total_tokens),
            ),
            float(
                inputs.get(
                    "max_elapsed_seconds", settings.agent_max_elapsed_seconds
                )
            ),
            _positive_budget(
                "max_embedding_requests",
                inputs.get(
                    "max_embedding_requests",
                    settings.agent_max_embedding_requests,
                ),
            ),
            _positive_budget(
                "max_embedding_inputs",
                inputs.get(
                    "max_embedding_inputs", settings.agent_max_embedding_inputs
                ),
            ),
        )

    def _starting_state(self, inputs, config):
        if isinstance(inputs, dict):
            return dict(inputs)
        if config is None or not hasattr(self.compiled_graph, "get_state"):
            raise ValueError(
                "A checkpoint resume requires config with configurable.thread_id"
            )
        snapshot = self.compiled_graph.get_state(config)
        values = getattr(snapshot, "values", None)
        if not values:
            raise ValueError("No checkpoint state exists for the supplied thread_id")
        return dict(values)

    def _stream_unlocked(self, inputs, config=None):
        starting_state = self._starting_state(inputs, config)
        (
            max_requests,
            max_tokens,
            max_elapsed_seconds,
            max_embedding_requests,
            max_embedding_inputs,
        ) = self._limits(starting_state)
        if max_elapsed_seconds <= 0:
            raise ValueError(
                "max_elapsed_seconds must be greater than zero, "
                f"got {max_elapsed_seconds}"
            )
        settings = get_settings()
        ledger = BudgetLedger(
            max_requests,
            max_tokens,
            initial_requests=starting_state.get("model_requests", 0),
            initial_tokens=starting_state.get("total_tokens", 0),
            accounting_complete=starting_state.get(
                "token_accounting_available", True
            ),
            max_elapsed_seconds=max_elapsed_seconds,
            initial_elapsed_seconds=starting_state.get("elapsed_seconds", 0.0),
            max_embedding_requests=max_embedding_requests,
            max_embedding_inputs=max_embedding_inputs,
            initial_embedding_requests=starting_state.get("embedding_requests", 0),
            initial_embedding_inputs=starting_state.get("embedding_inputs", 0),
        )
        graph_stream = None
        last_state = starting_state
        last_node = None
        initial_usage = {
            "model_requests": int(starting_state.get("model_requests", 0)),
            "input_tokens": int(starting_state.get("input_tokens", 0)),
            "output_tokens": int(starting_state.get("output_tokens", 0)),
            "total_tokens": int(starting_state.get("total_tokens", 0)),
        }
        previous_usage = dict(initial_usage)
        measured_trace = {}
        with activate_budget(ledger), get_openai_callback() as usage:
            try:
                graph_stream = self.compiled_graph.stream(inputs, config=config)
                for chunk in graph_stream:
                    node_name, raw_state = next(iter(chunk.items()))
                    # Modern LangGraph emits a synthetic interrupt marker whose
                    # value is a tuple, not graph State. The preceding node state
                    # is already checkpointed and remains the caller-facing result.
                    if node_name == "__interrupt__":
                        continue
                    current_usage = {
                        "model_requests": max(
                            ledger.requests_started,
                            initial_usage["model_requests"]
                            + usage.successful_requests,
                        ),
                        "input_tokens": initial_usage["input_tokens"]
                        + usage.prompt_tokens,
                        "output_tokens": initial_usage["output_tokens"]
                        + usage.completion_tokens,
                        "total_tokens": max(
                            ledger.tokens_committed,
                            initial_usage["total_tokens"] + usage.total_tokens,
                        ),
                    }
                    trace_events = [
                        dict(event) for event in (raw_state.get("trace_events") or [])
                    ]
                    for event in trace_events:
                        measurement = measured_trace.get(
                            (event.get("sequence"), event.get("node"))
                        )
                        if measurement:
                            event.update(measurement)
                    for index in range(len(trace_events) - 1, -1, -1):
                        if trace_events[index].get("node") == node_name:
                            measurement = {
                                key: current_usage[key] - previous_usage[key]
                                for key in current_usage
                            }
                            measurement["token_accounting_available"] = (
                                usage.total_tokens > 0
                            )
                            trace_events[index].update(measurement)
                            measured_trace[
                                (
                                    trace_events[index].get("sequence"),
                                    trace_events[index].get("node"),
                                )
                            ] = measurement
                            break
                    state = {
                        **raw_state,
                        "max_model_requests": max_requests,
                        "max_total_tokens": max_tokens,
                        "max_elapsed_seconds": max_elapsed_seconds,
                        "max_embedding_requests": max_embedding_requests,
                        "max_embedding_inputs": max_embedding_inputs,
                        "embedding_requests": ledger.embedding_requests,
                        "embedding_inputs": ledger.embedding_inputs,
                        **current_usage,
                        "token_accounting_available": ledger.accounting_complete,
                        "budget_mode": "hard_preflight_with_boundary_fallback",
                        "budget_diagnostics": ledger.snapshot(),
                        "trace_events": trace_events,
                    }
                    previous_usage = current_usage
                    last_state = state
                    last_node = node_name
                    if state.get("termination_reason"):
                        state = _persist_if_enabled(state, settings)
                        yield {node_name: state}
                        return
                    yield {node_name: state}
                    reason = None
                    if current_usage["model_requests"] > max_requests:
                        reason = "model_request_budget_exhausted"
                    elif current_usage["total_tokens"] > max_tokens:
                        reason = "token_budget_exhausted"
                    elif ledger.deadline_exhausted():
                        reason = "execution_deadline_exhausted"
                    if reason:
                        stopped = _persist_if_enabled(
                            stop_for_runtime_budget(
                                state,
                                reason,
                                usage,
                                ledger.snapshot(),
                                "node_boundary_fallback",
                            ),
                            settings,
                        )
                        yield {
                            "budget_exhausted": stopped
                        }
                        return
            except ModelBudgetExceeded as error:
                stopped = _persist_if_enabled(
                    stop_for_runtime_budget(
                        last_state,
                        error.reason,
                        type(
                            "CumulativeUsage",
                            (),
                            {
                                "successful_requests": ledger.requests_started,
                                "prompt_tokens": initial_usage["input_tokens"]
                                + usage.prompt_tokens,
                                "completion_tokens": initial_usage["output_tokens"]
                                + usage.completion_tokens,
                                "total_tokens": ledger.tokens_committed,
                            },
                        )(),
                        error.diagnostics,
                    ),
                    settings,
                )
                yield {
                    "budget_exhausted": stopped
                }
            except Exception as error:
                diagnostics = {
                    "status": "error",
                    "error_type": type(error).__name__,
                    "last_completed_node": last_node,
                    "step_count": last_state.get("step_count", 0),
                    "retrieval_count": last_state.get("retrieval_count", 0),
                    "evidence_count": len(last_state.get("evidence_records") or []),
                    "model_requests": last_state.get("model_requests", 0),
                    **(getattr(error, "diagnostics", None) or {}),
                }
                error.diagnostics = diagnostics
                _persist_if_enabled(
                    {
                        **last_state,
                        "termination_reason": "execution_error",
                        "error_diagnostics": diagnostics,
                    },
                    settings,
                )
                raise
            finally:
                if graph_stream is not None:
                    graph_stream.close()

    def stream(self, inputs, config=None):
        thread_id = self._checkpoint_thread_id(config)
        self._claim_thread(thread_id)
        try:
            yield from self._stream_unlocked(inputs, config=config)
        finally:
            self._release_thread(thread_id)

    def invoke(self, inputs, config=None):
        final_state = self._starting_state(inputs, config)
        for chunk in self.stream(inputs, config=config):
            final_state = next(iter(chunk.values()))
        return final_state

    def get_graph(self, *args, **kwargs):
        return self.compiled_graph.get_graph(*args, **kwargs)

    def get_state(self, config):
        """Expose a persisted thread snapshot without leaking it into logs."""
        return self.compiled_graph.get_state(config)

    def delete_thread(self, thread_id):
        """Apply an explicit retention action to one checkpoint thread."""
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise ValueError("thread_id must be a non-empty string")
        checkpointer = getattr(self.compiled_graph, "checkpointer", None)
        if checkpointer is None or not hasattr(checkpointer, "delete_thread"):
            raise RuntimeError("This Agent has no deletable persistent checkpointer")
        checkpointer.delete_thread(thread_id)
