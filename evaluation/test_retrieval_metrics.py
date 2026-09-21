import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from evaluation.run_retrieval_evaluation import (
    evaluate_case,
    marker_recall,
    ranked_relevance_metrics,
)


class RetrievalMetricTests(unittest.TestCase):
    def test_human_chunk_hashes_override_marker_proxy(self):
        gold = SimpleNamespace(page_content="gold text", metadata={"page": 1})
        proxy = SimpleNamespace(page_content="shared marker", metadata={"page": 2})
        store = Mock()
        store.similarity_search_with_score.return_value = [(proxy, 0.1), (gold, 0.2)]
        from hashlib import sha256
        gold_hash = sha256(b"gold text").hexdigest()
        case = {
            "id": "x", "category": "single_hop", "question": "q",
            "evidence": ["shared marker"],
            "review": {"gold_evidence_chunk_sha256": [gold_hash]},
        }
        result = evaluate_case(store, [gold, proxy], case, [1, 2])
        self.assertEqual(result["relevance_source"], "human_exact_chunk_hashes")
        self.assertEqual(result["hit@1"], 0.0)
        self.assertEqual(result["hit@2"], 1.0)

    def test_ranked_metrics_reward_early_relevant_documents(self):
        metrics = ranked_relevance_metrics([False, True, True], total_relevant=2, k=3)
        self.assertEqual(metrics["hit@3"], 1.0)
        self.assertEqual(metrics["precision@3"], 0.6667)
        self.assertEqual(metrics["recall@3"], 1.0)
        self.assertEqual(metrics["mrr@3"], 0.5)
        self.assertGreater(metrics["ndcg@3"], 0)
        self.assertLess(metrics["ndcg@3"], 1)

    def test_ranked_metrics_handle_no_relevant_result(self):
        metrics = ranked_relevance_metrics([False, False], total_relevant=1, k=2)
        self.assertEqual(metrics["hit@2"], 0.0)
        self.assertEqual(metrics["recall@2"], 0.0)
        self.assertEqual(metrics["mrr@2"], 0.0)
        self.assertEqual(metrics["ndcg@2"], 0.0)

    def test_marker_recall_tracks_each_evidence_component(self):
        value, hits = marker_recall(
            ["the first clue appears here", "unrelated text"],
            ["first clue", "second clue"],
        )
        self.assertEqual(value, 0.5)
        self.assertEqual(hits, [True, False])


if __name__ == "__main__":
    unittest.main()
