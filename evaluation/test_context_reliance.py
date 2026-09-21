import unittest

from evaluation.run_context_reliance_evaluation import (
    score_case_outputs,
    validate_cases,
)

CASE = {
    "id": "nonce-x",
    "category": "test",
    "question": "value?",
    "correct_context": "The value is Cedar-12.",
    "correct_answer": "Cedar-12",
    "counterfactual_context": "The value is Birch-29.",
    "counterfactual_answer": "Birch-29",
}


class ContextRelianceTests(unittest.TestCase):
    def test_valid_nonce_pair_passes_contract(self):
        self.assertEqual(validate_cases([CASE]), [])

    def test_duplicate_and_context_answer_mismatch_are_rejected(self):
        bad = {**CASE, "correct_context": "No value here."}
        errors = validate_cases([bad, bad])
        self.assertTrue(any("omits its answer" in error for error in errors))
        self.assertTrue(any("duplicate id" in error for error in errors))

    def test_counterfactual_pair_cannot_change_entity_identity(self):
        bad = {
            **CASE,
            "counterfactual_context": "The other record value is Birch-29.",
        }
        self.assertTrue(
            any("differ only" in error for error in validate_cases([bad]))
        )

    def test_score_requires_both_contexts_to_control_the_answer(self):
        scores = score_case_outputs(CASE, {
            "no_context": "NOT_ENOUGH_INFORMATION",
            "correct_context": "Cedar-12",
            "counterfactual_context": "Birch-29",
        })
        self.assertFalse(scores["direct_prior_leak"])
        self.assertTrue(scores["direct_abstention"])
        self.assertTrue(scores["context_switch_success"])

    def test_memorized_or_context_insensitive_answer_fails(self):
        scores = score_case_outputs(CASE, {
            "no_context": "Cedar-12",
            "correct_context": "Cedar-12",
            "counterfactual_context": "Cedar-12",
        })
        self.assertTrue(scores["direct_prior_leak"])
        self.assertFalse(scores["counterfactual_follow_accuracy"])
        self.assertFalse(scores["context_switch_success"])


if __name__ == "__main__":
    unittest.main()
