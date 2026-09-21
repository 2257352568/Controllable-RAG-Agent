"""Control regressions using the compiled graph and a real temporary FAISS index."""

import pickle
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

import faiss
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from controllable_rag.citations import make_evidence_record
from controllable_rag.config import Settings
from controllable_rag.graph import create_agent, get_retrieval_workflow
from controllable_rag.nodes import (
    assess_answerability,
    finalize_answer,
    retrieve_quotes,
)
from controllable_rag.policy import validate_evidence_minimum, validate_sources
from controllable_rag.retrieval import get_retriever


class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0]


class RetrievalPolicyTests(unittest.TestCase):
    def test_entrypoints_reject_ambiguous_or_invalid_policy_types(self):
        for sources in ([], "chunks", None, ["chunks", "chunks"], ["web"], [None]):
            with self.subTest(sources=sources), self.assertRaises(ValueError):
                validate_sources(sources)
        for minimum in (0, -1, True, 1.9, "2", None):
            with self.subTest(minimum=minimum), self.assertRaises(ValueError):
                validate_evidence_minimum(minimum)
        with self.assertRaises(ValueError):
            Settings(enabled_retrieval_sources=("web",))
        with self.assertRaises(ValueError):
            Settings(min_evidence_records=1.2)

    def test_duplicate_evidence_cannot_pass_either_gate_or_trigger_model_calls(self):
        state = {
            "question": "q", "min_evidence_records": 2,
            "evidence_records": [
                {"id": "same"}, {"id": "same"}, {"id": ""}, "malformed"
            ],
        }
        with patch("controllable_rag.nodes.get_agent_chains") as chains:
            assessment = assess_answerability(state)
        chains.assert_not_called()
        self.assertEqual(assessment["route_decision"], "insufficient")
        self.assertIn("evidence 1", assessment["evidence_gate_reason"])
        with patch("controllable_rag.graph.get_answer_workflow") as answer:
            final = finalize_answer(state)
        answer.assert_not_called()
        self.assertEqual(final["termination_reason"], "evidence_threshold_not_met")

    def test_direct_retrieval_node_cannot_bypass_disabled_source(self):
        with patch("controllable_rag.graph.get_retrieval_workflow") as workflow:
            result = retrieve_quotes({"enabled_retrieval_sources": ["chunks"]})
        workflow.assert_not_called()
        self.assertEqual(result["source_policy_events"][0]["source"], "quotes")

    def test_direct_subgraph_rejects_disabled_source_before_any_io(self):
        with patch("controllable_rag.nodes.get_retriever") as load:
            with self.assertRaisesRegex(ValueError, "disabled"):
                get_retrieval_workflow("quotes").invoke({
                    "question": "q", "enabled_retrieval_sources": ["chunks"],
                })
        load.assert_not_called()


class CompiledSourceControlTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "知识库"
        self.embeddings = LocalEmbeddings()
        self.doc = Document(page_content="The train leaves from Platform Nine and Three-Quarters.", metadata={"page": 1})
        self.record = make_evidence_record("chunks", 1, self.doc)
        store = FAISS.from_documents([self.doc], self.embeddings)
        directory = self.root / "chunks_vector_store"
        directory.mkdir(parents=True)
        with (directory / "index.faiss").open("wb") as stream:
            faiss.write_index(store.index, faiss.PyCallbackIOWriter(stream.write))
        with (directory / "index.pkl").open("wb") as stream:
            pickle.dump((store.docstore, store.index_to_docstore_id), stream)
        self.settings = Settings(
            project_root=self.root, enabled_retrieval_sources=("chunks",),
        )
        get_retriever.cache_clear()
        self.addCleanup(get_retriever.cache_clear)

    def chains(self, selected_tools):
        task_handler = Mock()
        task_handler.invoke.side_effect = [
            SimpleNamespace(tool=tool, query="platform", curr_context="")
            for tool in selected_tools
        ]
        def chain(result):
            return SimpleNamespace(invoke=Mock(return_value=result))

        return SimpleNamespace(
            anonymize_question=chain(SimpleNamespace(anonymized_question="platform", mapping={})),
            planner=chain(SimpleNamespace(steps=["find platform"])),
            break_down_plan=chain(SimpleNamespace(steps=["find platform"])),
            task_handler=task_handler,
            replanner=chain(SimpleNamespace(steps=["find platform"])),
            keep_relevant_content=chain(SimpleNamespace(relevant_content=self.doc.page_content, supporting_ids=[self.record["id"]])),
            ground_distillation=chain(SimpleNamespace(grounded=True, explanation="supported")),
            can_answer=chain(SimpleNamespace(can_be_answered=True, explanation="supported")),
            answer_from_context=chain(SimpleNamespace(
                answer_based_on_content="Platform Nine and Three-Quarters.",
                claim_citations=[{
                    "claim": "Platform Nine and Three-Quarters.",
                    "supporting_ids": [self.record["id"]],
                }],
            )),
            ground_answer=chain(SimpleNamespace(grounded=True, explanation="supported")),
        )

    def run_graph(self, chains, minimum, steps):
        with (
            patch("controllable_rag.nodes.get_agent_chains", return_value=chains),
            patch("controllable_rag.nodes.get_settings", return_value=self.settings),
            patch("controllable_rag.retrieval.get_settings", return_value=self.settings),
            patch("controllable_rag.retrieval.create_embedding_model", return_value=self.embeddings),
            patch("controllable_rag.nodes.get_retriever", wraps=get_retriever) as accessor,
        ):
            result = create_agent().invoke({
                "question": "Which platform?", "enabled_retrieval_sources": ["chunks"],
                "min_evidence_records": minimum, "max_steps": steps,
            }, config={"recursion_limit": 50})
        accessor.assert_called_once_with("chunks")
        return result

    def test_disabled_choice_recovers_using_allowed_source_and_real_index(self):
        chains = self.chains(["retrieve_quotes", "retrieve_chunks"])
        result = self.run_graph(chains, minimum=1, steps=2)
        self.assertEqual(result["termination_reason"], "answered")
        self.assertEqual(result["retrieval_count"], 1)
        self.assertEqual(result["attempted_retrieval_sources"], ["chunks"])
        self.assertEqual(result["step_count"], 2)
        self.assertEqual(result["citations"][0]["source"], "chunks")
        self.assertEqual(result["source_policy_events"][0]["source"], "quotes")
        self.assertIn("retrieval_source_disabled", [event["node"] for event in result["trace_events"]])
        feedback = chains.replanner.invoke.call_args_list[0].args[0]
        self.assertEqual(chains.replanner.invoke.call_count, 1)
        self.assertIn("did not retrieve", feedback["policy_feedback"])
        self.assertEqual(feedback["enabled_sources"], "chunks")
        self.assertEqual(chains.can_answer.invoke.call_count, 1)
        self.assertFalse((self.root / "book_quotes_vectorstore").exists())
        self.assertFalse((self.root / "chapter_summaries_vector_store").exists())

    def test_unmet_minimum_refuses_in_full_graph_despite_positive_fake_judge(self):
        chains = self.chains(["retrieve_chunks"])
        result = self.run_graph(chains, minimum=2, steps=1)
        self.assertEqual(result["termination_reason"], "step_budget_exhausted")
        self.assertIn("below required minimum 2", result["evidence_gate_reason"])
        self.assertEqual(result["citations"], [])
        chains.can_answer.invoke.assert_not_called()
        chains.replanner.invoke.assert_not_called()
        chains.answer_from_context.invoke.assert_not_called()


if __name__ == "__main__":
    unittest.main()
