import unittest
from types import SimpleNamespace

from evaluation.run_chunking_ablation import (
    reconstruct_pages,
    reconstruction_fidelity,
    split_pages,
)


class ChunkingAblationTests(unittest.TestCase):
    def test_reconstruct_pages_removes_exact_overlap_and_preserves_page_order(self):
        chunks = [
            SimpleNamespace(page_content="abc shared", metadata={"page": 2}),
            SimpleNamespace(page_content=" shared xyz", metadata={"page": 2}),
            SimpleNamespace(page_content="first", metadata={"page": 1}),
        ]
        pages = reconstruct_pages(chunks)
        self.assertEqual([page.metadata["page"] for page in pages], [1, 2])
        self.assertEqual(pages[1].page_content, "abc shared xyz")

    def test_split_pages_respects_character_limit(self):
        pages = [SimpleNamespace(page_content="word " * 100, metadata={"page": 1})]
        chunks = split_pages(pages, chunk_size=100, overlap=20)
        self.assertGreater(len(chunks), 1)
        self.assertLessEqual(max(len(chunk.page_content) for chunk in chunks), 100)

    def test_reconstruction_fidelity_reports_positional_and_unique_matches(self):
        def document(text):
            return SimpleNamespace(page_content=text, metadata={})

        result = reconstruction_fidelity(
            [document("a"), document("b")], [document("a"), document("changed")]
        )
        self.assertEqual(result["positional_exact_matches"], 1)
        self.assertEqual(result["positional_match_rate"], 0.5)
        self.assertEqual(result["unique_original_hash_coverage"], 0.5)


if __name__ == "__main__":
    unittest.main()
