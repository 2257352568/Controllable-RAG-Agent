import unittest
from unittest.mock import patch, sentinel

from langchain_core.runnables import RunnableLambda

from controllable_rag.chains import build_agent_chains, get_agent_chains
from controllable_rag.retrieval import get_retrievers


class FakeStructuredChatModel:
    def __init__(self):
        self.schemas = []

    def with_structured_output(self, schema):
        self.schemas.append(schema)
        return RunnableLambda(lambda value: value)


class LazyDependencyTests(unittest.TestCase):
    def tearDown(self):
        get_agent_chains.cache_clear()
        get_retrievers.cache_clear()

    def test_all_chains_share_one_injected_chat_model(self):
        chat_model = FakeStructuredChatModel()
        chains = build_agent_chains(chat_model)
        self.assertEqual(len(chat_model.schemas), 10)
        self.assertIsNotNone(chains.planner)
        self.assertIsNotNone(chains.task_handler)

    @patch("controllable_rag.chains.build_agent_chains", return_value=sentinel.chains)
    def test_agent_chains_are_created_once_on_first_access(self, build_chains):
        get_agent_chains.cache_clear()
        self.assertEqual(build_chains.call_count, 0)
        self.assertIs(get_agent_chains(), sentinel.chains)
        self.assertIs(get_agent_chains(), sentinel.chains)
        build_chains.assert_called_once_with()

    @patch("controllable_rag.retrieval.create_retrievers", return_value=sentinel.retrievers)
    def test_retrievers_are_loaded_once_on_first_access(self, create_retrievers):
        get_retrievers.cache_clear()
        self.assertEqual(create_retrievers.call_count, 0)
        self.assertIs(get_retrievers(), sentinel.retrievers)
        self.assertIs(get_retrievers(), sentinel.retrievers)
        create_retrievers.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
