import unittest
from unittest.mock import patch

from langchain_core.embeddings import Embeddings

from controllable_rag.budget import BudgetedChatModel, BudgetedEmbeddingModel
from controllable_rag.config import Settings
from controllable_rag.models import create_chat_model, create_embedding_model
from controllable_rag.resilience import CircuitBreakerModel, shared_circuit_breaker


class ModelFactoryTests(unittest.TestCase):
    def setUp(self):
        shared_circuit_breaker.cache_clear()
        self.settings = Settings(
            api_key="test-key",
            base_url="https://example.invalid/v1",
            chat_model="test-chat",
            embedding_model="test-embedding",
            embedding_dimensions=1536,
            max_retries=3,
            request_timeout_seconds=42,
        )

    @patch("controllable_rag.models.ChatOpenAI")
    def test_chat_factory_applies_provider_compatibility(self, chat_class):
        model = create_chat_model(max_tokens=321, settings=self.settings)
        self.assertIsInstance(model, CircuitBreakerModel)
        self.assertIsInstance(model._target, BudgetedChatModel)
        chat_class.assert_called_once_with(
            api_key="test-key",
            base_url="https://example.invalid/v1",
            model="test-chat",
            temperature=0,
            max_tokens=321,
            max_retries=3,
            timeout=42,
            model_kwargs={"extra_body": {"enable_thinking": False}},
        )

    @patch("controllable_rag.models.OpenAIEmbeddings")
    def test_embedding_factory_applies_index_dimensions(self, embedding_class):
        model = create_embedding_model(settings=self.settings)
        self.assertIsInstance(model, CircuitBreakerModel)
        self.assertIsInstance(model, Embeddings)
        self.assertIsInstance(model._target, BudgetedEmbeddingModel)
        embedding_class.assert_called_once_with(
            api_key="test-key",
            base_url="https://example.invalid/v1",
            model="test-embedding",
            dimensions=1536,
            chunk_size=10,
            max_retries=3,
            timeout=42,
            check_embedding_ctx_length=False,
        )


if __name__ == "__main__":
    unittest.main()
