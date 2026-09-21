import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from controllable_rag.budget import (
    BudgetedChatModel,
    BudgetedEmbeddingModel,
    BudgetLedger,
    ModelBudgetExceeded,
    activate_budget,
)
from controllable_rag.runtime import BoundedAgent, stop_for_runtime_budget


class MutableUsage:
    successful_requests = 0
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0


class FakeCompiledGraph:
    def __init__(self, usage, terminal=False):
        self.usage = usage
        self.terminal = terminal

    def stream(self, inputs, config=None):
        self.usage.successful_requests = 0
        self.usage.prompt_tokens = 0
        self.usage.completion_tokens = 0
        self.usage.total_tokens = 0
        yield {
            "initialize": {
                **inputs,
                "trace_events": [
                    {
                        "sequence": 1,
                        "node": "initialize",
                        "duration_ms": 0.1,
                        "status": "ok",
                    }
                ],
            }
        }
        self.usage.successful_requests = 2
        self.usage.prompt_tokens = 80
        self.usage.completion_tokens = 20
        self.usage.total_tokens = 100
        state = {
            **inputs,
            "trace_events": [
                {
                    "sequence": 1,
                    "node": "initialize",
                    "duration_ms": 0.1,
                    "status": "ok",
                },
                {
                    "sequence": 2,
                    "node": "sample_node",
                    "duration_ms": 1.0,
                    "status": "ok",
                }
            ],
        }
        if self.terminal:
            state.update(termination_reason="answered", response="done")
        yield {"sample_node": state}

    def get_graph(self):
        return "graph"


def callback_factory(usage):
    @contextmanager
    def fake_callback():
        yield usage

    return fake_callback


class RuntimeBudgetTests(unittest.TestCase):
    def test_graph_failure_exposes_safe_last_state_diagnostics(self):
        class FailingGraph:
            def stream(_self, inputs, config=None):
                yield {"replan": {
                    **inputs,
                    "step_count": 7,
                    "retrieval_count": 4,
                    "evidence_records": [{"secret": "do not expose"}],
                    "trace_events": [],
                }}
                raise RuntimeError("graph stopped")

        usage = MutableUsage()
        with patch(
            "controllable_rag.runtime.get_openai_callback",
            callback_factory(usage),
        ):
            with self.assertRaises(RuntimeError) as raised:
                BoundedAgent(FailingGraph()).invoke({
                    "question": "private question",
                    "max_model_requests": 10,
                    "max_total_tokens": 1000,
                })
        diagnostics = raised.exception.diagnostics
        self.assertEqual(diagnostics["last_completed_node"], "replan")
        self.assertEqual(diagnostics["step_count"], 7)
        self.assertEqual(diagnostics["retrieval_count"], 4)
        self.assertEqual(diagnostics["evidence_count"], 1)
        self.assertNotIn("private question", str(diagnostics))
        self.assertNotIn("do not expose", str(diagnostics))

    def test_request_is_rejected_before_provider_when_limit_is_spent(self):
        provider = SimpleNamespace(invoke=lambda *_args, **_kwargs: None)
        model = BudgetedChatModel(provider, max_output_tokens=10)
        ledger = BudgetLedger(max_requests=1, max_tokens=10000)
        with activate_budget(ledger):
            model.invoke("first")
            with self.assertRaises(ModelBudgetExceeded) as raised:
                model.invoke("second")
        self.assertEqual(raised.exception.reason, "model_request_budget_exhausted")
        self.assertEqual(ledger.requests_started, 1)

    def test_token_reservation_rejects_before_provider_call(self):
        calls = []
        provider = SimpleNamespace(invoke=lambda *_args, **_kwargs: calls.append(1))
        model = BudgetedChatModel(provider, max_output_tokens=100)
        ledger = BudgetLedger(max_requests=10, max_tokens=100)
        with activate_budget(ledger):
            with self.assertRaises(ModelBudgetExceeded) as raised:
                model.invoke("input")
        self.assertEqual(raised.exception.reason, "token_budget_exhausted")
        self.assertEqual(calls, [])
        self.assertEqual(ledger.requests_started, 0)

    def test_embedding_request_budget_rejects_before_provider(self):
        calls = []
        provider = SimpleNamespace(
            embed_query=lambda text: calls.append(text) or [1.0]
        )
        model = BudgetedEmbeddingModel(provider)
        ledger = BudgetLedger(
            10, 10000, max_embedding_requests=1, max_embedding_inputs=5
        )
        with activate_budget(ledger):
            self.assertEqual(model.embed_query("first"), [1.0])
            with self.assertRaises(ModelBudgetExceeded) as raised:
                model.embed_query("second")
        self.assertEqual(raised.exception.reason, "embedding_request_budget_exhausted")
        self.assertEqual(calls, ["first"])
        self.assertEqual(ledger.embedding_requests, 1)

    def test_embedding_input_budget_counts_document_batches(self):
        calls = []
        provider = SimpleNamespace(
            embed_documents=lambda texts: calls.append(texts) or [[1.0]] * len(texts)
        )
        model = BudgetedEmbeddingModel(provider)
        ledger = BudgetLedger(
            10, 10000, max_embedding_requests=5, max_embedding_inputs=2
        )
        with activate_budget(ledger):
            with self.assertRaises(ModelBudgetExceeded) as raised:
                model.embed_documents(["a", "b", "c"])
        self.assertEqual(raised.exception.reason, "embedding_input_budget_exhausted")
        self.assertEqual(calls, [])
        self.assertEqual(ledger.embedding_inputs, 0)

    def test_execution_deadline_rejects_before_provider_call(self):
        now = [0.0]
        calls = []
        provider = SimpleNamespace(invoke=lambda *_args, **_kwargs: calls.append(1))
        ledger = BudgetLedger(
            max_requests=10,
            max_tokens=10000,
            max_elapsed_seconds=1.0,
            clock=lambda: now[0],
        )
        now[0] = 1.1
        with activate_budget(ledger):
            with self.assertRaises(ModelBudgetExceeded) as raised:
                BudgetedChatModel(provider, 10).invoke("input")
        self.assertEqual(raised.exception.reason, "execution_deadline_exhausted")
        self.assertEqual(calls, [])

    def test_execution_deadline_stops_at_node_boundary(self):
        class OneNodeGraph:
            def stream(_self, inputs, config=None):
                yield {"slow": {**inputs, "trace_events": []}}

        class JumpClock:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                return 0.0 if self.calls == 1 else 2.0

        def ledger_factory(*args, **kwargs):
            return BudgetLedger(*args, **kwargs, clock=JumpClock())

        with patch("controllable_rag.runtime.BudgetLedger", side_effect=ledger_factory):
            result = BoundedAgent(OneNodeGraph()).invoke(
                {
                    "max_model_requests": 10,
                    "max_total_tokens": 10000,
                    "max_elapsed_seconds": 1.0,
                }
            )
        self.assertEqual(result["termination_reason"], "execution_deadline_exhausted")
        self.assertGreaterEqual(result["elapsed_seconds"], 1.0)

    def test_actual_usage_replaces_conservative_reservation(self):
        message = SimpleNamespace(
            usage_metadata={"total_tokens": 23}, response_metadata={}
        )
        provider = SimpleNamespace(invoke=lambda *_args, **_kwargs: message)
        ledger = BudgetLedger(max_requests=2, max_tokens=1000)
        with activate_budget(ledger):
            result = BudgetedChatModel(provider, 10).invoke("input")
        self.assertIs(result, message)
        self.assertEqual(ledger.tokens_committed, 23)
        self.assertEqual(ledger.tokens_reserved, 0)
        self.assertTrue(ledger.accounting_complete)

    def test_missing_usage_keeps_reservation_and_marks_accounting_incomplete(self):
        provider = SimpleNamespace(invoke=lambda *_args, **_kwargs: "result")
        ledger = BudgetLedger(max_requests=2, max_tokens=1000)
        with activate_budget(ledger):
            BudgetedChatModel(provider, 10).invoke("x")
        self.assertGreater(ledger.tokens_committed, 10)
        self.assertFalse(ledger.accounting_complete)

    def test_structured_output_is_unwrapped_after_exact_usage_settlement(self):
        raw = SimpleNamespace(
            usage_metadata={"total_tokens": 31}, response_metadata={}
        )
        structured = SimpleNamespace(
            invoke=lambda *_args, **_kwargs: {
                "raw": raw, "parsed": "parsed-value", "parsing_error": None
            }
        )
        provider = SimpleNamespace(
            with_structured_output=lambda *_args, **_kwargs: structured
        )
        ledger = BudgetLedger(max_requests=2, max_tokens=2000)
        with activate_budget(ledger):
            result = BudgetedChatModel(provider, 20).with_structured_output(
                {"type": "object"}
            ).invoke("input")
        self.assertEqual(result, "parsed-value")
        self.assertEqual(ledger.tokens_committed, 31)
        self.assertTrue(ledger.accounting_complete)

    def test_structured_output_is_also_unwrapped_without_active_budget(self):
        raw = SimpleNamespace(usage_metadata={"total_tokens": 31}, response_metadata={})
        structured = SimpleNamespace(
            invoke=lambda *_args, **_kwargs: {
                "raw": raw, "parsed": "parsed-value", "parsing_error": None
            }
        )
        provider = SimpleNamespace(
            with_structured_output=lambda *_args, **_kwargs: structured
        )
        result = BudgetedChatModel(provider, 20).with_structured_output(
            {"type": "object"}
        ).invoke("input")
        self.assertEqual(result, "parsed-value")

    def test_request_budget_stops_at_node_boundary_and_records_actual_usage(self):
        usage = MutableUsage()
        agent = BoundedAgent(FakeCompiledGraph(usage))
        with patch(
            "controllable_rag.runtime.get_openai_callback",
            callback_factory(usage),
        ):
            chunks = list(
                agent.stream(
                    {
                        "question": "q",
                        "max_model_requests": 1,
                        "max_total_tokens": 1000,
                    }
                )
            )

        final = chunks[-1]["budget_exhausted"]
        measured_event = chunks[1]["sample_node"]["trace_events"][-1]
        self.assertEqual(measured_event["model_requests"], 2)
        self.assertEqual(measured_event["total_tokens"], 100)
        prior_event = chunks[1]["sample_node"]["trace_events"][0]
        self.assertEqual(prior_event["model_requests"], 0)
        self.assertEqual(prior_event["total_tokens"], 0)
        self.assertEqual(final["termination_reason"], "model_request_budget_exhausted")
        self.assertEqual(final["model_requests"], 2)
        self.assertEqual(final["total_tokens"], 100)
        self.assertEqual(final["trace_events"][-1]["status"], "budget_exhausted")
        self.assertEqual(
            final["trace_events"][-1]["budget_enforcement"],
            "node_boundary_fallback",
        )

    def test_token_budget_has_distinct_machine_readable_reason(self):
        usage = MutableUsage()
        agent = BoundedAgent(FakeCompiledGraph(usage))
        with patch(
            "controllable_rag.runtime.get_openai_callback",
            callback_factory(usage),
        ):
            result = agent.invoke(
                {
                    "question": "q",
                    "max_model_requests": 10,
                    "max_total_tokens": 50,
                }
            )
        self.assertEqual(result["termination_reason"], "token_budget_exhausted")
        self.assertTrue(result["token_accounting_available"])
        incomplete = stop_for_runtime_budget(
            {"token_accounting_available": True},
            "token_budget_exhausted",
            usage,
            {"budget_accounting_complete": False},
        )
        self.assertFalse(incomplete["token_accounting_available"])

    def test_existing_terminal_state_is_not_overwritten(self):
        usage = MutableUsage()
        agent = BoundedAgent(FakeCompiledGraph(usage, terminal=True))
        with patch(
            "controllable_rag.runtime.get_openai_callback",
            callback_factory(usage),
        ):
            result = agent.invoke(
                {
                    "question": "q",
                    "max_model_requests": 1,
                    "max_total_tokens": 50,
                }
            )
        self.assertEqual(result["termination_reason"], "answered")
        self.assertEqual(result["response"], "done")

    def test_non_positive_budgets_are_rejected(self):
        agent = BoundedAgent(SimpleNamespace())
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            list(
                agent.stream(
                    {
                        "max_model_requests": 0,
                        "max_total_tokens": 100,
                    }
                )
            )

    def test_get_graph_delegates_to_compiled_graph(self):
        usage = MutableUsage()
        self.assertEqual(BoundedAgent(FakeCompiledGraph(usage)).get_graph(), "graph")


if __name__ == "__main__":
    unittest.main()
