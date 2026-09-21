import unittest
from types import SimpleNamespace

from evaluation.run_private_rag_reliance_evaluation import (
    documents_for,
    retrieval_record,
)


class PrivateRagRelianceTests(unittest.TestCase):
    def test_documents_keep_case_and_variant_provenance(self):
        cases = [{"id": "x", "correct_context": "fact"}]
        document = documents_for(cases, "correct_context")[0]
        self.assertEqual(document.page_content, "fact")
        self.assertEqual(document.metadata, {"case_id": "x", "variant": "correct_context"})

    def test_retrieval_record_checks_expected_top_one_and_hashes_content(self):
        document = SimpleNamespace(page_content="fact", metadata={"case_id": "x", "variant": "correct_context"})
        record = retrieval_record([(document, 0.25)], "x")
        self.assertTrue(record["top1_correct"])
        self.assertEqual(record["ranked"][0]["distance"], 0.25)
        self.assertEqual(len(record["ranked"][0]["content_sha256"]), 64)

    def test_retrieval_record_detects_wrong_or_empty_top_one(self):
        wrong = SimpleNamespace(page_content="fact", metadata={"case_id": "other", "variant": "correct_context"})
        self.assertFalse(retrieval_record([(wrong, 1.0)], "x")["top1_correct"])
        self.assertFalse(retrieval_record([], "x")["top1_correct"])


if __name__ == "__main__":
    unittest.main()
