import unittest

from evaluation.judge_review import (
    JUDGE_REVIEW_VERSION,
    build_audit_report,
    record_key,
    record_sha256,
    select_audit_records,
    validate_review,
)


def record(case_id, system="direct", category="single_hop"):
    return {
        "case_id": case_id,
        "system": system,
        "category": category,
        "repeat_index": 1,
        "question": "q",
        "reference_answer": "reference",
        "answer": "answer",
        "error": None,
        "judge_context_audit_evidence": [],
        "judge": {"correctness": 0.8, "relevance": 1.0, "faithfulness": None},
    }


def review(target, details_sha="d" * 64, **overrides):
    value = {
        "record_key": record_key(target),
        "record_sha256": record_sha256(target),
        "details_sha256": details_sha,
        "reviewer": "human-1",
        "reviewed_at": "2026-09-12T12:00:00+08:00",
        "review_version": JUDGE_REVIEW_VERSION,
        "human_scores": {"correctness": 1.0, "relevance": 1.0},
    }
    value.update(overrides)
    return value


class JudgeReviewTests(unittest.TestCase):
    def test_review_schema_requires_core_scores_and_real_hex_digests(self):
        target = record("a-001")
        invalid = review(
            target,
            record_sha256="z" * 64,
            human_scores={"faithfulness": True},
        )
        errors = validate_review(invalid)
        self.assertTrue(any("record_sha256" in error for error in errors))
        self.assertTrue(any("human_scores missing" in error for error in errors))
        self.assertTrue(any("invalid human score" in error for error in errors))

    def test_selection_is_deterministic_and_stratified(self):
        records = [record(f"a-{index:03d}") for index in range(10)]
        records += [record(f"b-{index:03d}", "naive-rag", "multi_hop") for index in range(5)]
        first = select_audit_records(records, rate=0.2, seed=7)
        second = select_audit_records(records, rate=0.2, seed=7)
        self.assertEqual([record_key(item) for item in first], [record_key(item) for item in second])
        self.assertEqual(len(first), 3)
        self.assertEqual({item["system"] for item in first}, {"direct", "naive-rag"})

    def test_audit_report_calculates_agreement(self):
        target = record("a-001")
        report = build_audit_report(
            [target], [target], [(1, review(target))], "d" * 64, tolerance=0.2
        )
        self.assertTrue(report["complete"])
        self.assertTrue(report["quality_gate_passed"])
        self.assertEqual(report["effective_selection_rate"], 1.0)
        self.assertEqual(report["metrics"]["correctness"]["mean_absolute_error"], 0.2)
        self.assertEqual(report["metrics"]["correctness"]["agreement_within_tolerance"], 1.0)

    def test_completed_but_inaccurate_judge_fails_predeclared_quality_gate(self):
        target = record("a-001")
        bad_review = review(
            target, human_scores={"correctness": 0.0, "relevance": 0.0}
        )
        report = build_audit_report(
            [target], [target], [(1, bad_review)], "d" * 64
        )
        self.assertTrue(report["complete"])
        self.assertFalse(report["quality_gate_passed"])
        self.assertFalse(report["metrics"]["correctness"]["quality_gate_passed"])

    def test_changed_details_or_record_invalidates_review(self):
        target = record("a-001")
        stale_details = build_audit_report(
            [target], [target], [(1, review(target))], "e" * 64
        )
        changed = {**target, "answer": "changed"}
        stale_record = build_audit_report(
            [changed], [changed], [(1, review(target))], "d" * 64
        )
        self.assertFalse(stale_details["complete"])
        self.assertFalse(stale_record["complete"])
        self.assertEqual(stale_details["stale_record_keys"], [record_key(target)])
        self.assertEqual(stale_record["stale_record_keys"], [record_key(target)])


if __name__ == "__main__":
    unittest.main()
