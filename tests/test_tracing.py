import json
import unittest
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from controllable_rag.config import Settings
from controllable_rag.observability import ObservedNodeError
from controllable_rag.runtime import BoundedAgent
from controllable_rag.tracing import (
    build_trace_payload,
    persist_trace,
    verify_trace,
)
from tests.test_runtime_budget import FakeCompiledGraph, MutableUsage, callback_factory


def terminal_state(trace_id):
    return {
        "trace_id": trace_id,
        "termination_reason": "answered",
        "question": "private-question",
        "response": "private-answer",
        "aggregated_context": "private-context",
        "model_requests": 1,
        "input_tokens": 10,
        "output_tokens": 2,
        "total_tokens": 12,
        "token_accounting_available": True,
        "max_embedding_requests": 4,
        "max_embedding_inputs": 8,
        "embedding_requests": 2,
        "embedding_inputs": 2,
        "trace_events": [{
            "sequence": 1, "node": "answer", "status": "ok",
            "content": "private-event-content",
        }],
        "budget_diagnostics": {
            "tokens_committed": 12, "provider_message": "private-provider-error"
        },
        "error_diagnostics": {
            "node": "planner",
            "error_type": "CircuitOpenError",
            "status": "rejected",
            "circuit_state": "open",
            "retry_after_seconds": 4.2,
            "provider_url": "private-provider-url",
        },
    }


class TracePersistenceTests(unittest.TestCase):
    def test_payload_allowlist_excludes_prompts_answers_context_and_error_text(self):
        payload = build_trace_payload(terminal_state(str(uuid4())))
        serialized = json.dumps(payload)
        for secret in (
            "private-question", "private-answer", "private-context",
            "private-event-content", "private-provider-error",
            "private-provider-url",
        ):
            self.assertNotIn(secret, serialized)
        self.assertEqual(payload["events"][0]["node"], "answer")
        self.assertEqual(payload["budget_diagnostics"]["tokens_committed"], 12)
        self.assertEqual(payload["error_diagnostics"]["circuit_state"], "open")
        self.assertEqual(payload["error_diagnostics"]["retry_after_seconds"], 4.2)
        self.assertEqual(payload["control"]["embedding_requests"], 2)
        self.assertEqual(payload["control"]["embedding_inputs"], 2)
        self.assertEqual(payload["control"]["claim_citation_count"], 0)

    def test_persisted_trace_verifies_and_tampering_fails(self):
        with TemporaryDirectory() as directory:
            target = persist_trace(terminal_state(str(uuid4())), directory)
            self.assertEqual(verify_trace(target), (True, "ok"))
            envelope = json.loads(target.read_text(encoding="utf-8"))
            envelope["payload"]["termination_reason"] = "tampered"
            target.write_text(json.dumps(envelope), encoding="utf-8")
            self.assertEqual(verify_trace(target), (False, "payload hash mismatch"))

    def test_verifier_accepts_known_previous_schema_but_rejects_unknown(self):
        with TemporaryDirectory() as directory:
            target = persist_trace(terminal_state(str(uuid4())), directory)
            envelope = json.loads(target.read_text(encoding="utf-8"))
            for previous_version in ("2026-09-12.1", "2026-09-13.1"):
                envelope["payload"]["schema_version"] = previous_version
                canonical = json.dumps(
                    envelope["payload"], ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                envelope["payload_sha256"] = sha256(canonical).hexdigest()
                target.write_text(json.dumps(envelope), encoding="utf-8")
                self.assertEqual(verify_trace(target), (True, "ok"))

            envelope["payload"]["schema_version"] = "unknown"
            canonical = json.dumps(
                envelope["payload"], ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            envelope["payload_sha256"] = sha256(canonical).hexdigest()
            target.write_text(json.dumps(envelope), encoding="utf-8")
            self.assertEqual(verify_trace(target), (False, "unsupported schema version"))

    def test_existing_trace_id_cannot_be_overwritten(self):
        with TemporaryDirectory() as directory:
            state = terminal_state(str(uuid4()))
            target = persist_trace(state, directory)
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):
                persist_trace(state, directory)
            self.assertEqual(target.read_bytes(), original)

    def test_bounded_agent_persists_terminal_trace_before_return(self):
        with TemporaryDirectory() as directory:
            trace_id = str(uuid4())
            settings = Settings(
                trace_enabled=True, trace_directory=Path(directory)
            )
            usage = MutableUsage()
            agent = BoundedAgent(FakeCompiledGraph(usage, terminal=True))
            with (
                patch("controllable_rag.runtime.get_settings", return_value=settings),
                patch(
                    "controllable_rag.runtime.get_openai_callback",
                    callback_factory(usage),
                ),
            ):
                result = agent.invoke({
                    "trace_id": trace_id, "trace_enabled": True,
                    "max_model_requests": 10, "max_total_tokens": 1000,
                })
            target = Path(result["trace_path"])
            self.assertTrue(result["trace_persisted"])
            self.assertTrue(target.exists())
            self.assertEqual(verify_trace(target), (True, "ok"))

    def test_persistence_failure_does_not_replace_terminal_result(self):
        usage = MutableUsage()
        settings = Settings(trace_enabled=True)
        agent = BoundedAgent(FakeCompiledGraph(usage, terminal=True))
        with (
            patch("controllable_rag.runtime.get_settings", return_value=settings),
            patch("controllable_rag.runtime.persist_trace", side_effect=OSError("disk")),
            patch(
                "controllable_rag.runtime.get_openai_callback",
                callback_factory(usage),
            ),
        ):
            result = agent.invoke({
                "trace_id": str(uuid4()), "trace_enabled": True,
                "max_model_requests": 10, "max_total_tokens": 1000,
            })
        self.assertEqual(result["termination_reason"], "answered")
        self.assertFalse(result["trace_persisted"])
        self.assertEqual(result["trace_persistence_error"], "OSError")

    def test_node_failure_persists_safe_partial_trace_and_still_raises(self):
        class FailingGraph:
            def stream(_self, inputs, config=None):
                yield {"initialize": {
                    **inputs,
                    "trace_events": [{
                        "sequence": 1, "node": "initialize", "status": "ok"
                    }],
                }}
                raise ObservedNodeError("planner", 12.5, "TimeoutError")

        with TemporaryDirectory() as directory:
            trace_id = str(uuid4())
            settings = Settings(trace_enabled=True, trace_directory=Path(directory))
            usage = MutableUsage()
            agent = BoundedAgent(FailingGraph())
            with (
                patch("controllable_rag.runtime.get_settings", return_value=settings),
                patch(
                    "controllable_rag.runtime.get_openai_callback",
                    callback_factory(usage),
                ),
                self.assertRaises(ObservedNodeError),
            ):
                agent.invoke({
                    "trace_id": trace_id, "trace_enabled": True,
                    "max_model_requests": 10, "max_total_tokens": 1000,
                })
            target = Path(directory) / f"{trace_id}.json"
            self.assertEqual(verify_trace(target), (True, "ok"))
            payload = json.loads(target.read_text(encoding="utf-8"))["payload"]
            self.assertEqual(payload["termination_reason"], "execution_error")
            self.assertEqual(payload["error_diagnostics"]["node"], "planner")
            self.assertEqual(payload["error_diagnostics"]["error_type"], "TimeoutError")


if __name__ == "__main__":
    unittest.main()
