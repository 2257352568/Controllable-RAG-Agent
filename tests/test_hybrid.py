import unittest

from controllable_rag.hybrid import reciprocal_rank_fusion


class ReciprocalRankFusionTests(unittest.TestCase):
    def test_consensus_can_outrank_single_retriever_first_place(self):
        fused = reciprocal_rank_fusion(
            [["dense-only", "shared"], ["shared", "bm25-only"]],
            limit=3,
            rank_constant=60,
        )
        self.assertEqual([key for key, _ in fused], ["shared", "dense-only", "bm25-only"])

    def test_duplicates_in_one_list_do_not_add_extra_votes(self):
        fused = reciprocal_rank_fusion([["a", "a"], ["b"]], limit=2, rank_constant=0)
        self.assertEqual(dict(fused)["a"], 1.0)
        self.assertEqual(dict(fused)["b"], 1.0)

    def test_ties_follow_first_appearance_deterministically(self):
        fused = reciprocal_rank_fusion([["z"], ["a"]], limit=2)
        self.assertEqual([key for key, _ in fused], ["z", "a"])

    def test_invalid_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([], limit=1)
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([["a"]], limit=0)
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([["a"]], limit=1, rank_constant=-1)


if __name__ == "__main__":
    unittest.main()
