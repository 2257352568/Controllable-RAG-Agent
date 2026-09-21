import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from types import SimpleNamespace

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from controllable_rag.budget import BudgetedChatModel, BudgetedEmbeddingModel
from controllable_rag.checkpointing import open_sqlite_agent
from controllable_rag.graph import create_agent
from controllable_rag.observability import observed_node
from controllable_rag.runtime import BoundedAgent, ConcurrentThreadExecutionError


class BudgetState(TypedDict, total=False):
    max_model_requests: int
    max_total_tokens: int
    model_requests: int
    total_tokens: int
    token_accounting_available: bool
    max_embedding_requests: int
    max_embedding_inputs: int
    embedding_requests: int
    embedding_inputs: int
    trace_events: list
    termination_reason: str


class CheckpointingTests(unittest.TestCase):
    def test_main_graph_sqlite_checkpoint_is_opt_in_and_thread_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "agent.sqlite"
            config_a = {"configurable": {"thread_id": "thread-a"}}
            config_b = {"configurable": {"thread_id": "thread-b"}}

            connection = sqlite3.connect(database, check_same_thread=False)
            try:
                agent = create_agent(
                    checkpointer=SqliteSaver(connection),
                    interrupt_before=["anonymize_question"],
                )
                result = agent.invoke(
                    {
                        "question": "private checkpoint marker",
                        "max_model_requests": 4,
                        "max_total_tokens": 4000,
                    },
                    config=config_a,
                )
                self.assertEqual(result["curr_state"], "initialize")
            finally:
                connection.close()

            reopened = sqlite3.connect(database, check_same_thread=False)
            try:
                agent = create_agent(
                    checkpointer=SqliteSaver(reopened),
                    interrupt_before=["anonymize_question"],
                )
                state_a = agent.compiled_graph.get_state(config_a)
                state_b = agent.compiled_graph.get_state(config_b)
                self.assertEqual(state_a.values["question"], "private checkpoint marker")
                self.assertEqual(state_a.next, ("anonymize_question",))
                self.assertFalse(state_b.values)
            finally:
                reopened.close()

    def test_resume_uses_checkpointed_cumulative_request_budget(self):
        calls = []

        def provider_call(*_args, **_kwargs):
            calls.append(1)
            return SimpleNamespace(
                usage_metadata={"total_tokens": 10}, response_metadata={}
            )

        model = BudgetedChatModel(SimpleNamespace(invoke=provider_call), 1)

        def call_model(state):
            model.invoke("checkpoint budget probe")
            return dict(state)

        workflow = StateGraph(BudgetState)
        workflow.add_node("first", observed_node("first", call_model))
        workflow.add_node("second", observed_node("second", call_model))
        workflow.set_entry_point("first")
        workflow.add_edge("first", "second")
        workflow.add_edge("second", END)
        saver = InMemorySaver()
        config = {"configurable": {"thread_id": "budget-thread"}}
        agent = BoundedAgent(
            workflow.compile(checkpointer=saver, interrupt_after=["first"])
        )

        paused = agent.invoke(
            {"max_model_requests": 1, "max_total_tokens": 1000}, config=config
        )
        self.assertEqual(paused["model_requests"], 1)
        self.assertEqual(paused["total_tokens"], 10)
        self.assertEqual(agent.compiled_graph.get_state(config).values["model_requests"], 1)

        resumed = agent.invoke(None, config=config)
        self.assertEqual(resumed["termination_reason"], "model_request_budget_exhausted")
        self.assertEqual(resumed["model_requests"], 1)
        self.assertEqual(calls, [1])

    def test_resume_uses_checkpointed_cumulative_token_budget(self):
        calls = []

        def provider_call(*_args, **_kwargs):
            calls.append(1)
            return SimpleNamespace(
                usage_metadata={"total_tokens": 10}, response_metadata={}
            )

        model = BudgetedChatModel(SimpleNamespace(invoke=provider_call), 1)

        def call_model(state):
            model.invoke("checkpoint budget probe")
            return dict(state)

        workflow = StateGraph(BudgetState)
        workflow.add_node("first", observed_node("first", call_model))
        workflow.add_node("second", observed_node("second", call_model))
        workflow.set_entry_point("first")
        workflow.add_edge("first", "second")
        workflow.add_edge("second", END)
        config = {"configurable": {"thread_id": "token-budget-thread"}}
        agent = BoundedAgent(
            workflow.compile(checkpointer=InMemorySaver(), interrupt_after=["first"])
        )

        paused = agent.invoke(
            {"max_model_requests": 10, "max_total_tokens": 540}, config=config
        )
        self.assertEqual(paused["total_tokens"], 10)
        resumed = agent.invoke(None, config=config)
        self.assertEqual(resumed["termination_reason"], "token_budget_exhausted")
        self.assertEqual(resumed["total_tokens"], 10)
        self.assertEqual(calls, [1])

    def test_resume_uses_checkpointed_embedding_budget(self):
        calls = []
        model = BudgetedEmbeddingModel(
            SimpleNamespace(
                embed_query=lambda text: calls.append(text) or [1.0]
            )
        )

        def embed(state):
            model.embed_query("checkpoint embedding probe")
            return dict(state)

        workflow = StateGraph(BudgetState)
        workflow.add_node("first", observed_node("first", embed))
        workflow.add_node("second", observed_node("second", embed))
        workflow.set_entry_point("first")
        workflow.add_edge("first", "second")
        workflow.add_edge("second", END)
        config = {"configurable": {"thread_id": "embedding-budget-thread"}}
        agent = BoundedAgent(
            workflow.compile(checkpointer=InMemorySaver(), interrupt_after=["first"])
        )
        paused = agent.invoke(
            {
                "max_model_requests": 10,
                "max_total_tokens": 10000,
                "max_embedding_requests": 1,
                "max_embedding_inputs": 5,
            },
            config=config,
        )
        self.assertEqual(paused["embedding_requests"], 1)
        self.assertEqual(paused["embedding_inputs"], 1)
        resumed = agent.invoke(None, config=config)
        self.assertEqual(
            resumed["termination_reason"], "embedding_request_budget_exhausted"
        )
        self.assertEqual(calls, ["checkpoint embedding probe"])

    def test_resume_requires_an_existing_thread_checkpoint(self):
        agent = create_agent(checkpointer=InMemorySaver())
        with self.assertRaisesRegex(ValueError, "No checkpoint state"):
            agent.invoke(None, config={"configurable": {"thread_id": "missing"}})

    def test_sqlite_agent_supports_explicit_thread_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "nested" / "agent.sqlite"
            config = {"configurable": {"thread_id": "delete-me"}}
            with open_sqlite_agent(
                database, interrupt_before=["anonymize_question"]
            ) as agent:
                agent.invoke(
                    {
                        "question": "retention probe",
                        "max_model_requests": 4,
                        "max_total_tokens": 4000,
                    },
                    config=config,
                )
                self.assertTrue(agent.get_state(config).values)
                agent.delete_thread("delete-me")
                self.assertFalse(agent.get_state(config).values)
            self.assertTrue(database.is_file())

    def test_shared_sqlite_agent_keeps_parallel_thread_states_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "parallel.sqlite"
            with open_sqlite_agent(
                database, interrupt_before=["anonymize_question"]
            ) as agent:
                def execute(index):
                    config = {"configurable": {"thread_id": f"thread-{index}"}}
                    marker = f"parallel-marker-{index}"
                    agent.invoke(
                        {
                            "question": marker,
                            "max_model_requests": 4,
                            "max_total_tokens": 4000,
                        },
                        config=config,
                    )
                    return marker, agent.get_state(config).values["question"]

                with ThreadPoolExecutor(max_workers=8) as executor:
                    results = list(executor.map(execute, range(32)))
            self.assertTrue(all(expected == stored for expected, stored in results))

    def test_same_thread_concurrent_execution_fails_fast(self):
        entered = Event()
        release = Event()

        class BlockingGraph:
            checkpointer = object()

            def stream(_self, inputs, config=None):
                entered.set()
                release.wait(timeout=2)
                yield {"node": {**inputs, "trace_events": []}}

        agent = BoundedAgent(BlockingGraph())
        config = {"configurable": {"thread_id": "shared-thread"}}
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(agent.invoke, {"max_model_requests": 2,
                "max_total_tokens": 2000}, config)
            self.assertTrue(entered.wait(timeout=1))
            with self.assertRaises(ConcurrentThreadExecutionError):
                agent.invoke(
                    {"max_model_requests": 2, "max_total_tokens": 2000},
                    config=config,
                )
            release.set()
            self.assertEqual(first.result()["max_model_requests"], 2)


if __name__ == "__main__":
    unittest.main()
