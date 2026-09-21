import unittest
from types import SimpleNamespace

from evaluation.export_review_packet import render_review_packet


class ReviewPacketTests(unittest.TestCase):
    def test_packet_is_bounded_hash_bound_and_cannot_claim_approval(self):
        case = {
            "id": "x-001", "category": "unanswerable", "question": "Missing fact?",
            "reference_answer": "Not stated.", "acceptable_answers": ["not stated"],
            "answerable": False, "review_search_terms": ["needle"],
            "risk_tags": ["knowledge_absence"],
        }
        documents = [SimpleNamespace(
            page_content="prefix needle " + "x" * 1000, metadata={"page": 7}
        )]
        rendered = render_review_packet(
            [case], documents, "a" * 64, [("dataset.jsonl", "b" * 64)]
        )
        self.assertIn("Corpus index SHA256: `" + "a" * 64, rendered)
        self.assertIn("chunk SHA256", rendered)
        self.assertIn("not proof of absence", rendered)
        self.assertIn("Risk tags: `knowledge_absence`", rendered)
        self.assertIn("Checking boxes here does not create an approval", rendered)
        self.assertNotIn("x" * 300, rendered)


if __name__ == "__main__":
    unittest.main()
