import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from uuid import UUID

from fastapi.testclient import TestClient

from controllable_rag.api import create_api
from controllable_rag.config import Settings
from controllable_rag.index_manifest import STORE_DIRECTORIES, write_index_manifest


class StubAgent:
    def __init__(self, chunks=None, error=None):
        self.chunks = chunks or []
        self.error = error
        self.last_inputs = None

    def stream(self, inputs, config=None):
        self.last_inputs = inputs
        if self.error:
            raise self.error
        yield from self.chunks

    def invoke(self, inputs, config=None):
        self.last_inputs = inputs
        if self.error:
            raise self.error
        return next(iter(self.chunks[-1].values()))


def parse_sse(body):
    events = []
    for frame in body.strip().split("\n\n"):
        fields = {}
        for line in frame.splitlines():
            key, value = line.split(": ", 1)
            fields[key] = value
        fields["data"] = json.loads(fields["data"])
        events.append(fields)
    return events


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.state = {
            "curr_state": "get_final_answer",
            "response": "Grounded answer",
            "termination_reason": "answered",
            "aggregated_context": "PRIVATE RETRIEVED TEXT",
            "grounding_explanation": "PRIVATE INTERNAL EXPLANATION",
            "step_count": 3,
            "retrieval_count": 1,
            "model_requests": 2,
            "total_tokens": 42,
            "citations": [
                {
                    "id": "chunks-p1-abc",
                    "source": "chunks",
                    "rank": 1,
                    "metadata": {"page": 1, "private": "do not expose"},
                },
                {
                    "id": "quotes-doc-def",
                    "source": "quotes",
                    "rank": 2,
                    "metadata": {
                        "location_candidates": [43, 186],
                        "private": "do not expose",
                    },
                },
            ],
            "claim_citations": [{
                "claim": "Grounded answer",
                "supporting_ids": ["chunks-p1-abc", "invented-id"],
                "private": "do not expose",
            }],
            "trace_id": "trace-1",
        }

    def client(self, agent):
        return TestClient(create_api(lambda: agent, max_concurrent_requests=8))

    @staticmethod
    def create_fake_indexes(root):
        for source, directory_name in STORE_DIRECTORIES.items():
            target = root / directory_name
            target.mkdir()
            (target / "index.faiss").write_bytes(f"{source}-index".encode())
            (target / "index.pkl").write_bytes(b"not-a-real-pickle")
        write_index_manifest(root, "text-embedding-v4", 1536)

    def test_health_is_lazy(self):
        calls = []
        client = TestClient(create_api(
            lambda: calls.append("constructed"), max_concurrent_requests=1
        ))
        self.assertEqual(client.get("/health").json(), {"status": "ok"})
        self.assertEqual(calls, [])

    def test_readiness_checks_key_and_enabled_index_files_without_agent(self):
        calls = []
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_fake_indexes(root)
            settings = Settings(
                project_root=root,
                api_key="configured-secret",
                enabled_retrieval_sources=("chunks", "quotes"),
            )
            client = TestClient(create_api(
                lambda: calls.append("constructed"),
                max_concurrent_requests=1,
                settings=settings,
            ))
            response = client.get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")
        self.assertEqual(response.json()["scope"], "local_prerequisites_only")
        self.assertEqual(set(response.json()["components"]["indexes"]), {"chunks", "quotes"})
        self.assertNotIn("configured-secret", response.text)
        self.assertEqual(calls, [])
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_readiness_rejects_integrity_or_embedding_contract_mismatch(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_fake_indexes(root)
            chunks = root / STORE_DIRECTORIES["chunks"] / "index.faiss"
            chunks.write_bytes(b"tampered-after-manifest")
            settings = Settings(
                project_root=root, api_key="key",
                enabled_retrieval_sources=("chunks",),
            )
            response = TestClient(create_api(
                lambda: StubAgent(), max_concurrent_requests=1, settings=settings
            )).get("/ready")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(
                response.json()["components"]["indexes"]["chunks"]["status"],
                "integrity_mismatch",
            )

            write_index_manifest(root, "text-embedding-v4", 1536)
            wrong_model = Settings(
                project_root=root, api_key="key", embedding_model="other-model",
                enabled_retrieval_sources=("chunks",),
            )
            response = TestClient(create_api(
                lambda: StubAgent(), max_concurrent_requests=1, settings=wrong_model
            )).get("/ready")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(
                response.json()["components"]["embedding_contract"]["status"],
                "mismatch",
            )

    def test_readiness_fails_closed_without_exposing_paths_or_secrets(self):
        with TemporaryDirectory() as directory:
            settings = Settings(
                project_root=Path(directory),
                api_key=None,
                enabled_retrieval_sources=("chunks",),
            )
            client = TestClient(create_api(
                lambda: StubAgent(), max_concurrent_requests=1, settings=settings
            ))
            response = client.get("/ready")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "not_ready")
        self.assertEqual(response.json()["components"]["api_key"]["status"], "missing")
        self.assertEqual(
            response.json()["components"]["manifest"]["status"], "missing"
        )
        self.assertEqual(
            response.json()["components"]["indexes"]["chunks"]["status"], "missing"
        )
        self.assertNotIn(str(settings.project_root), response.text)

    def test_query_returns_whitelisted_result(self):
        agent = StubAgent([{"final": self.state}])
        response = self.client(agent).post(
            "/v1/query", json={"question": " Who taught the class? "}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["response"], "Grounded answer")
        self.assertEqual(body["citations"][0]["page"], 1)
        self.assertEqual(body["citations"][1]["page_candidates"], [43, 186])
        self.assertEqual(body["claim_citations"], [{
            "claim": "Grounded answer", "supporting_ids": ["chunks-p1-abc"],
        }])
        self.assertNotIn("aggregated_context", body)
        self.assertNotIn("grounding_explanation", body)
        self.assertNotIn("private", body["citations"][0])
        self.assertNotIn("private", body["claim_citations"][0])
        self.assertEqual(agent.last_inputs["question"], "Who taught the class?")
        self.assertEqual(set(agent.last_inputs), {"question", "trace_id"})
        self.assertEqual(str(UUID(agent.last_inputs["trace_id"])), body["request_id"])

    def test_server_correlation_id_is_shared_and_cannot_be_supplied(self):
        agent = StubAgent([{"final": self.state}])
        client = self.client(agent)
        rejected = client.post(
            "/v1/query", json={"question": "test", "trace_id": str(UUID(int=0))}
        )
        self.assertEqual(rejected.status_code, 422)

        response = client.post("/v1/query", json={"question": "test"})
        body = response.json()
        self.assertEqual(response.headers["x-request-id"], body["request_id"])
        self.assertEqual(body["trace_id"], body["request_id"])
        self.assertEqual(agent.last_inputs["trace_id"], body["request_id"])
        self.assertEqual(str(UUID(body["request_id"])), body["request_id"])

    def test_agent_is_lazily_constructed_once_for_queries(self):
        calls = []
        agent = StubAgent([{"final": self.state}])

        def factory():
            calls.append("constructed")
            return agent

        client = TestClient(create_api(factory, max_concurrent_requests=1))
        self.assertEqual(calls, [])
        for _ in range(2):
            self.assertEqual(
                client.post("/v1/query", json={"question": "test"}).status_code,
                200,
            )
        self.assertEqual(calls, ["constructed"])

    def test_capacity_rejects_without_queueing_and_recovers(self):
        entered = Event()
        release = Event()

        class BlockingAgent(StubAgent):
            def invoke(self, inputs, config=None):
                entered.set()
                if not release.wait(timeout=2):
                    raise RuntimeError("test timed out")
                return self.chunks[-1]["final"]

        agent = BlockingAgent([{"final": self.state}])
        client = TestClient(create_api(lambda: agent, max_concurrent_requests=1))
        with ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(
                client.post, "/v1/query", json={"question": "first"}
            )
            self.assertTrue(entered.wait(timeout=1))
            overloaded = client.post("/v1/query", json={"question": "second"})
            self.assertEqual(overloaded.status_code, 429)
            self.assertEqual(overloaded.json()["error"], "server_overloaded")
            self.assertEqual(overloaded.headers["retry-after"], "1")
            release.set()
            self.assertEqual(first.result(timeout=2).status_code, 200)
        self.assertEqual(
            client.post("/v1/query", json={"question": "third"}).status_code,
            200,
        )

    def test_invalid_capacity_fails_at_startup(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            create_api(lambda: StubAgent(), max_concurrent_requests=0)

    def test_query_validation_fails_closed(self):
        client = self.client(StubAgent([{"final": self.state}]))
        for payload in (
            {"question": "   "},
            {"question": "ok", "max_steps": 0},
            {"question": "ok", "enabled_retrieval_sources": []},
            {"question": "ok", "enabled_retrieval_sources": ["chunks", "chunks"]},
            {"question": "ok", "unknown_control": True},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(
                    client.post("/v1/query", json=payload).status_code, 422
                )

    def test_query_sanitizes_execution_error(self):
        response = self.client(StubAgent(error=RuntimeError("secret-value"))).post(
            "/v1/query", json={"question": "test"}
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"], "agent_execution_failed")
        self.assertNotIn("secret-value", response.text)
        self.assertTrue(response.json()["request_id"])
        self.assertEqual(response.json()["trace_id"], response.json()["request_id"])
        self.assertEqual(response.headers["x-request-id"], response.json()["request_id"])

    def test_sse_contract_orders_events_and_excludes_private_state(self):
        chunks = [
            {"planner": {**self.state, "curr_state": "planner"}},
            {"final": self.state},
        ]
        response = self.client(StubAgent(chunks)).post(
            "/v1/query/stream", json={"question": "test"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        self.assertEqual(response.headers["cache-control"], "no-cache")
        self.assertTrue(response.headers["x-request-id"])
        events = parse_sse(response.text)
        self.assertEqual(
            [event["event"] for event in events],
            ["started", "progress", "progress", "completed"],
        )
        self.assertEqual([event["id"] for event in events], ["1", "2", "3", "4"])
        self.assertEqual(events[-1]["data"]["response"], "Grounded answer")
        self.assertEqual(
            response.headers["x-request-id"], events[0]["data"]["trace_id"]
        )
        self.assertEqual(
            events[0]["data"]["trace_id"], events[-1]["data"]["trace_id"]
        )
        self.assertNotIn("PRIVATE", response.text)

    def test_sse_reports_sanitized_terminal_error(self):
        response = self.client(
            StubAgent(error=RuntimeError("private-provider-message"))
        ).post("/v1/query/stream", json={"question": "test"})
        events = parse_sse(response.text)
        self.assertEqual([event["event"] for event in events], ["started", "error"])
        self.assertEqual(events[-1]["data"]["error"], "agent_execution_failed")
        self.assertNotIn("private-provider-message", response.text)


if __name__ == "__main__":
    unittest.main()
