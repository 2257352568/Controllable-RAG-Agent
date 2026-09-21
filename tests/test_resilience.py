import unittest
from types import SimpleNamespace

from controllable_rag.budget import BudgetedChatModel, BudgetLedger, activate_budget
from controllable_rag.observability import observed_node
from controllable_rag.resilience import (
    CircuitBreakerModel,
    CircuitOpenError,
    ProviderCircuitBreaker,
    is_transient_provider_error,
)


class APIConnectionError(RuntimeError):
    pass


class BadRequestError(RuntimeError):
    status_code = 400


class ResilienceTests(unittest.TestCase):
    def test_classifier_distinguishes_transient_and_contract_failures(self):
        self.assertTrue(is_transient_provider_error(APIConnectionError("network")))
        self.assertTrue(
            is_transient_provider_error(SimpleNamespace(status_code=503))
        )
        self.assertFalse(is_transient_provider_error(BadRequestError("bad input")))

    def test_open_circuit_rejects_without_consuming_another_budget_slot(self):
        calls = []

        def fail(*_args, **_kwargs):
            calls.append(1)
            raise APIConnectionError("provider unavailable")

        breaker = ProviderCircuitBreaker(1, 30)
        model = CircuitBreakerModel(
            BudgetedChatModel(SimpleNamespace(invoke=fail), 10), breaker
        )
        ledger = BudgetLedger(10, 10000)
        with activate_budget(ledger):
            with self.assertRaises(APIConnectionError):
                model.invoke("first")
            self.assertEqual(ledger.requests_started, 1)
            with self.assertRaises(CircuitOpenError) as raised:
                model.invoke("second")
        self.assertEqual(calls, [1])
        self.assertEqual(ledger.requests_started, 1)
        self.assertEqual(raised.exception.diagnostics["circuit_state"], "open")

    def test_half_open_success_closes_circuit(self):
        now = [0.0]
        breaker = ProviderCircuitBreaker(1, 5, clock=lambda: now[0])
        with self.assertRaises(APIConnectionError):
            breaker.call(lambda: (_ for _ in ()).throw(APIConnectionError("x")))
        with self.assertRaises(CircuitOpenError):
            breaker.call(lambda: "too early")
        now[0] = 5.0
        self.assertEqual(breaker.call(lambda: "probe-ok"), "probe-ok")
        self.assertEqual(breaker.call(lambda: "closed-ok"), "closed-ok")

    def test_permanent_error_does_not_open_circuit(self):
        breaker = ProviderCircuitBreaker(1, 5)
        for _ in range(2):
            with self.assertRaises(BadRequestError):
                breaker.call(lambda: (_ for _ in ()).throw(BadRequestError("bad")))

    def test_observed_node_preserves_safe_open_circuit_diagnostics(self):
        error = CircuitOpenError("open", 4.2)

        def reject(_state):
            raise error

        with self.assertRaises(CircuitOpenError) as raised:
            observed_node("planner", reject)({})
        self.assertEqual(raised.exception.diagnostics["node"], "planner")
        self.assertEqual(raised.exception.diagnostics["circuit_state"], "open")
        self.assertEqual(raised.exception.diagnostics["retry_after_seconds"], 4.2)


if __name__ == "__main__":
    unittest.main()
