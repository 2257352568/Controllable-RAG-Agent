import unittest
from types import SimpleNamespace

from evaluation.repair_quote_locations import (
    enrich_quote_documents,
    locate_quote_pages,
)


class QuoteLocationTests(unittest.TestCase):
    def test_unique_ambiguous_and_missing_locations_fail_closed(self):
        pages = [
            SimpleNamespace(page_content="Alpha exact quote. Other.", metadata={"page": 4}),
            SimpleNamespace(page_content="Repeated phrase.", metadata={"page": 8}),
            SimpleNamespace(page_content="Repeated   phrase.", metadata={"page": 9}),
        ]
        quotes = [
            SimpleNamespace(page_content="Alpha\nexact quote.", metadata={}),
            SimpleNamespace(page_content="Repeated phrase.", metadata={"page": 999}),
            SimpleNamespace(page_content="Absent phrase.", metadata={}),
        ]
        matches = locate_quote_pages(quotes, pages)
        report = enrich_quote_documents(quotes, matches)

        self.assertEqual(matches, [[4], [8, 9], []])
        self.assertEqual(quotes[0].metadata["page"], 4)
        self.assertNotIn("page", quotes[1].metadata)
        self.assertEqual(quotes[1].metadata["location_candidates"], [8, 9])
        self.assertNotIn("page", quotes[2].metadata)
        self.assertEqual(report["unique"], 1)
        self.assertEqual(report["ambiguous"], 1)
        self.assertEqual(report["missing"], 1)
        self.assertEqual(report["page_coverage"], 0.333333)


if __name__ == "__main__":
    unittest.main()
