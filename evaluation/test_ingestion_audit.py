import unittest
from types import SimpleNamespace

from evaluation.audit_ingestion import (
    chunk_overlap_statistics,
    document_statistics,
    exact_suffix_prefix_overlap,
    quote_location_statistics,
)


class IngestionAuditTests(unittest.TestCase):
    def test_exact_overlap_is_bounded(self):
        self.assertEqual(exact_suffix_prefix_overlap("abcXYZ", "XYZdef", 10), 3)
        self.assertEqual(exact_suffix_prefix_overlap("abcXYZ", "XYZdef", 2), 0)

    def test_document_and_same_page_overlap_statistics(self):
        documents = [
            SimpleNamespace(page_content="a" * 10 + " shared", metadata={"page": 1}),
            SimpleNamespace(page_content=" shared" + "b" * 8, metadata={"page": 1}),
            SimpleNamespace(page_content="other", metadata={"page": 2}),
        ]
        stats = document_statistics(documents)
        overlap = chunk_overlap_statistics(documents, 20)
        self.assertEqual(stats["documents"], 3)
        self.assertEqual(stats["metadata_fields"], ["page"])
        self.assertEqual(stats["metadata_coverage"], {"page": 3})
        self.assertEqual(overlap["same_page_pairs"], 1)
        self.assertEqual(overlap["max"], len(" shared"))

    def test_quote_location_contract_distinguishes_ambiguity_from_missing(self):
        documents = [
            SimpleNamespace(metadata={
                "page": 4,
                "location_match_status": "unique",
                "location_provenance": "exact",
            }),
            SimpleNamespace(metadata={
                "location_candidates": [8, 9],
                "location_match_status": "ambiguous",
                "location_provenance": "exact",
            }),
            SimpleNamespace(metadata={
                "location_match_status": "missing",
                "location_provenance": "exact",
            }),
            SimpleNamespace(metadata={"page": 99, "location_match_status": "ambiguous"}),
        ]
        stats = quote_location_statistics(documents)
        self.assertEqual(stats["unique"], 1)
        self.assertEqual(stats["ambiguous"], 2)
        self.assertEqual(stats["missing"], 1)
        self.assertEqual(stats["invalid"], 1)
        self.assertEqual(stats["page_coverage"], 0.25)


if __name__ == "__main__":
    unittest.main()
