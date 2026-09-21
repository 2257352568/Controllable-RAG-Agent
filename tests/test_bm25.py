import unittest

from controllable_rag.bm25 import BM25Index, tokenize


class BM25Tests(unittest.TestCase):
    def test_tokenization_is_case_and_punctuation_insensitive(self):
        self.assertEqual(tokenize("Hogwarts, EXPRESS!"), ["hogwarts", "express"])

    def test_rare_matching_document_ranks_first_deterministically(self):
        index = BM25Index(["common words", "rare platform nine", "rare unrelated"])
        self.assertEqual(index.search("platform nine", 2)[0], 1)
        self.assertEqual(index.search("missing", 3), [0, 1, 2])

    def test_invalid_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            BM25Index([])
        with self.assertRaises(ValueError):
            BM25Index(["text"], b=2)

