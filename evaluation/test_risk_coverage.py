import json
import tempfile
import unittest
from pathlib import Path

from evaluation.audit_risk_coverage import audit_datasets, summarize_coverage


def case(case_id, category, question, risk_tags=None):
    answerable = category not in {"unanswerable", "adversarial"}
    payload = {
        "id": case_id,
        "category": category,
        "question": question,
        "reference_answer": "answer" if answerable else "ask for clarification",
        "acceptable_answers": ["answer" if answerable else "clarify"],
        "evidence": ["answer"] if answerable else [],
        "answerable": answerable,
        "review_status": "needs_human_review",
    }
    if not answerable:
        payload["review_search_terms"] = ["term"]
    if risk_tags is not None:
        payload["risk_tags"] = risk_tags
    return payload


class RiskCoverageTests(unittest.TestCase):
    def test_coverage_counts_cases_once_per_tag_and_enforces_minimums(self):
        cases = [
            case("test-001", "adversarial", "Question one?", ["false_premise"]),
            case("test-002", "adversarial", "Question two?", ["false_premise"]),
        ]
        result = summarize_coverage(
            cases,
            {"adversarial": 2},
            {"false_premise": 2, "prompt_injection": 1},
        )
        self.assertEqual(result["risk_case_counts"]["false_premise"], 2)
        self.assertFalse(result["passed"])

    def test_cross_dataset_duplicates_and_untagged_negative_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.jsonl"
            second = root / "second.jsonl"
            duplicated = case("test-001", "unanswerable", "Same question?", [])
            first.write_text(json.dumps(duplicated) + "\n", encoding="utf-8")
            second.write_text(json.dumps(duplicated) + "\n", encoding="utf-8")
            report = audit_datasets(
                [first, second],
                {"unanswerable": 1},
                {"knowledge_absence": 0},
            )
        self.assertFalse(report["valid"])
        self.assertTrue(any("requires risk_tags" in error for error in report["errors"]))
        self.assertTrue(any("duplicate id" in error for error in report["errors"]))
        self.assertTrue(any("duplicate question" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
