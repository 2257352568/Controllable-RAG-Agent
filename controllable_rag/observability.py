"""Lightweight node-level tracing stored in LangGraph state."""

from functools import wraps
from time import perf_counter

from .budget import ModelBudgetExceeded, active_budget_state
from .resilience import CircuitOpenError


class ObservedNodeError(RuntimeError):
    """Attach safe structured node diagnostics without echoing provider messages."""

    def __init__(self, node, duration_ms, error_type):
        self.diagnostics = {
            "node": node,
            "duration_ms": duration_ms,
            "status": "error",
            "error_type": error_type,
        }
        super().__init__(f"Node {node!r} failed ({error_type})")


def observed_node(name, node):
    """Wrap a node and append stable, serializable timing metadata to its state."""

    @wraps(node)
    def wrapped(state):
        started = perf_counter()
        try:
            result = node(state)
        except ModelBudgetExceeded:
            # This is expected control flow handled by BoundedAgent, not a node failure.
            raise
        except CircuitOpenError as error:
            # Preserve safe breaker diagnostics for evaluation/trace reporting.
            error.diagnostics.update(
                node=name,
                duration_ms=round((perf_counter() - started) * 1000, 3),
            )
            raise
        except Exception as error:
            duration_ms = round((perf_counter() - started) * 1000, 3)
            raise ObservedNodeError(
                name, duration_ms, type(error).__name__
            ) from error

        trace_events = list(result.get("trace_events") or state.get("trace_events") or [])
        trace_events.append(
            {
                "sequence": len(trace_events) + 1,
                "node": name,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
                "status": "ok",
                "step_count": result.get("step_count", state.get("step_count", 0)),
                "tool": result.get("tool", state.get("tool", "")),
            }
        )
        result["trace_events"] = trace_events
        # These fields are returned by the node itself, so LangGraph includes the
        # cumulative ledger in its checkpoint rather than only in the outer stream.
        result.update(active_budget_state())
        return result

    return wrapped
