import unittest

from evaluation.audit_dataset import validate_cases, verify_evidence


def case(**overrides):
    value = {
        "id": "hp1-001",
        "category": "single_hop",
        "question": "What is the answer?",
        "reference_answer": "Alpha.",
        "acceptable_answers": ["alpha"],
        "evidence": ["source alpha"],
        "answerable": True,
        "review_status": "source_verified",
    }
    value.update(overrides)
    return value


class DatasetAuditTests(unittest.TestCase):
    def test_valid_case_passes_schema_validation(self):
        errors, warnings = validate_cases([(1, case())])
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_duplicate_question_and_id_are_rejected(self):
        errors, _ = validate_cases([(1, case()), (2, case())])
        self.assertTrue(any("duplicate id" in error for error in errors))
        self.assertTrue(any("duplicate normalized question" in error for error in errors))

    def test_formal_gate_requires_human_approval(self):
        errors, _ = validate_cases([(1, case())], require_human_approved=True)
        self.assertTrue(any("human_approved" in error for error in errors))

    def test_evidence_is_matched_to_corpus_pages(self):
        errors, matches = verify_evidence(
            [(1, case())], [{"text": "the source alpha passage", "page": 7}]
        )
        self.assertEqual(errors, [])
        self.assertEqual(matches["hp1-001"][0]["pages"], [7])

    def test_negative_cases_require_review_search_terms_but_no_positive_evidence(self):
        negative = case(
            category="unanswerable", answerable=False, evidence=[],
            risk_tags=["knowledge_absence"],
            review_status="needs_human_review",
        )
        errors, _ = validate_cases([(1, negative)])
        self.assertTrue(any("review_search_terms" in error for error in errors))
        negative["review_search_terms"] = ["bounded search term"]
        errors, _ = validate_cases([(1, negative)])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
