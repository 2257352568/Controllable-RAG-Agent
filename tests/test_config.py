import os
import unittest
from pathlib import Path
from unittest.mock import patch

from controllable_rag.config import Settings


class SettingsTests(unittest.TestCase):
    def test_qwen_key_has_precedence_over_legacy_names(self):
        environment = {
            "QWEN_API_KEY": "qwen-key",
            "DASHSCOPE_API_KEY": "dashscope-key",
            "OPENAI_API_KEY": "legacy-key",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings.from_env(Path.cwd())
        self.assertEqual(settings.api_key, "qwen-key")

    def test_legacy_openai_variable_remains_compatible(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "legacy-key"}, clear=True):
            settings = Settings.from_env(Path.cwd())
        self.assertEqual(settings.api_key, "legacy-key")

    def test_secret_is_not_exposed_by_repr(self):
        settings = Settings(api_key="top-secret")
        self.assertNotIn("top-secret", repr(settings))

    def test_positive_integer_validation(self):
        with patch.dict(os.environ, {"RAG_CHUNKS_TOP_K": "0"}, clear=True):
            with self.assertRaisesRegex(ValueError, "greater than zero"):
                Settings.from_env(Path.cwd())

    def test_execution_deadline_parsing_and_validation(self):
        with patch.dict(
            os.environ,
            {
                "AGENT_MAX_ELAPSED_SECONDS": "2.5",
                "QWEN_CIRCUIT_FAILURE_THRESHOLD": "4",
                "QWEN_CIRCUIT_RECOVERY_SECONDS": "7.5",
                "AGENT_MAX_EMBEDDING_REQUESTS": "6",
                "AGENT_MAX_EMBEDDING_INPUTS": "9",
                "RAG_API_MAX_CONCURRENT_REQUESTS": "3",
            },
            clear=True,
        ):
            settings = Settings.from_env(Path.cwd())
            self.assertEqual(settings.agent_max_elapsed_seconds, 2.5)
            self.assertEqual(settings.circuit_failure_threshold, 4)
            self.assertEqual(settings.circuit_recovery_seconds, 7.5)
            self.assertEqual(settings.agent_max_embedding_requests, 6)
            self.assertEqual(settings.agent_max_embedding_inputs, 9)
            self.assertEqual(settings.api_max_concurrent_requests, 3)
        for value in ("0", "not-a-number"):
            with self.subTest(value=value), patch.dict(
                os.environ, {"AGENT_MAX_ELAPSED_SECONDS": value}, clear=True
            ):
                with self.assertRaisesRegex(ValueError, "AGENT_MAX_ELAPSED_SECONDS"):
                    Settings.from_env(Path.cwd())

    def test_api_capacity_must_be_positive(self):
        for value in ("0", "not-a-number"):
            with self.subTest(value=value), patch.dict(
                os.environ, {"RAG_API_MAX_CONCURRENT_REQUESTS": value}, clear=True
            ):
                with self.assertRaisesRegex(ValueError, "RAG_API_MAX_CONCURRENT_REQUESTS"):
                    Settings.from_env(Path.cwd())
        for value in (0, 1.5, True):
            with self.subTest(direct=value), self.assertRaisesRegex(
                ValueError, "positive integer"
            ):
                Settings(api_max_concurrent_requests=value)

    def test_enabled_sources_and_minimum_evidence_are_parsed(self):
        with patch.dict(
            os.environ,
            {
                "RAG_ENABLED_SOURCES": "chunks,quotes",
                "RAG_MIN_EVIDENCE_RECORDS": "2",
            },
            clear=True,
        ):
            settings = Settings.from_env(Path.cwd())
        self.assertEqual(settings.enabled_retrieval_sources, ("chunks", "quotes"))
        self.assertEqual(settings.min_evidence_records, 2)

    def test_trace_configuration_resolves_relative_directory(self):
        root = Path.cwd()
        with patch.dict(
            os.environ,
            {"RAG_TRACE_ENABLED": "true", "RAG_TRACE_DIR": "private-traces"},
            clear=True,
        ):
            settings = Settings.from_env(root)
        self.assertTrue(settings.trace_enabled)
        self.assertEqual(
            settings.effective_trace_directory, (root / "private-traces").resolve()
        )

    def test_invalid_trace_boolean_is_rejected(self):
        with patch.dict(os.environ, {"RAG_TRACE_ENABLED": "sometimes"}, clear=True):
            with self.assertRaisesRegex(ValueError, "RAG_TRACE_ENABLED"):
                Settings.from_env(Path.cwd())

    def test_enabled_sources_fail_closed_for_empty_unknown_or_duplicate_values(self):
        for value in ("", "chunks,web", "chunks,chunks"):
            with self.subTest(value=value), patch.dict(
                os.environ, {"RAG_ENABLED_SOURCES": value}, clear=True
            ):
                with self.assertRaisesRegex(ValueError, "RAG_ENABLED_SOURCES"):
                    Settings.from_env(Path.cwd())

    def test_missing_key_has_actionable_error(self):
        for value in (None, "", "   "):
            with self.subTest(value=value), self.assertRaisesRegex(
                RuntimeError, "QWEN_API_KEY"
            ):
                Settings(api_key=value).require_api_key()
        with self.assertRaisesRegex(ValueError, "string or None"):
            Settings(api_key=123)


if __name__ == "__main__":
    unittest.main()
