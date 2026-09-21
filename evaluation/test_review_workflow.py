import unittest

from evaluation.review_workflow import (
    REVIEW_CHECKLIST_VERSION,
    case_content_sha256,
    latest_reviews,
    materialize_approved_cases,
    review_progress,
    validate_materialized_reviews,
    validate_review_records,
)


def case(**overrides):
    value = {
        "id": "hp1-001",
        "category": "single_hop",
        "question": "Question?",
        "reference_answer": "Answer.",
        "acceptable_answers": ["answer"],
        "evidence": ["evidence"],
        "answerable": True,
        "review_status": "source_verified",
    }
    value.update(overrides)
    return value


def review(target, **overrides):
    value = {
        "case_id": target["id"],
        "case_content_sha256": case_content_sha256(target),
        "decision": "approved",
        "reviewer": "reviewer-1",
        "reviewed_at": "2026-09-11T12:00:00+08:00",
        "checklist_version": REVIEW_CHECKLIST_VERSION,
        "corpus_index_sha256": "a" * 64,
        "gold_evidence_chunk_sha256": ["b" * 64] if target["answerable"] else [],
    }
    value.update(overrides)
    return value


class ReviewWorkflowTests(unittest.TestCase):
    def test_case_hash_ignores_review_metadata_but_not_semantic_edits(self):
        original = case()
        self.assertEqual(
            case_content_sha256(original),
            case_content_sha256(
                {**original, "review_status": "human_approved", "review": {"x": 1}}
            ),
        )
        self.assertNotEqual(
            case_content_sha256(original),
            case_content_sha256({**original, "reference_answer": "Changed."}),
        )

    def test_latest_append_only_decision_wins(self):
        target = case()
        records = [
            (1, review(target, decision="approved")),
            (2, review(target, decision="rejected")),
        ]
        self.assertEqual(latest_reviews(records)[target["id"]]["decision"], "rejected")

    def test_materialization_adds_verified_provenance(self):
        target = case()
        approved, errors = materialize_approved_cases(
            [target], [(1, review(target))], expected_corpus_sha256="a" * 64
        )
        self.assertEqual(errors, [])
        self.assertEqual(approved[0]["review_status"], "human_approved")
        self.assertEqual(approved[0]["review"]["reviewer"], "reviewer-1")
        self.assertEqual(
            approved[0]["review"]["checklist_version"], REVIEW_CHECKLIST_VERSION
        )
        self.assertEqual(
            approved[0]["review"]["case_content_sha256"],
            case_content_sha256(target),
        )
        self.assertEqual(approved[0]["review"]["gold_evidence_chunk_sha256"], ["b" * 64])

    def test_answerable_approval_requires_exact_gold_chunk(self):
        target = case()
        approved, errors = materialize_approved_cases(
            [target], [(1, review(target, gold_evidence_chunk_sha256=[]))]
        )
        self.assertEqual(approved, [])
        self.assertTrue(any("requires gold evidence chunks" in error for error in errors))

    def test_unanswerable_approval_rejects_positive_chunk_labels(self):
        target = case(answerable=False, evidence=[])
        approved, errors = materialize_approved_cases(
            [target], [(1, review(target, gold_evidence_chunk_sha256=["b" * 64]))]
        )
        self.assertEqual(approved, [])
        self.assertTrue(any("cannot include gold evidence chunks" in error for error in errors))

    def test_stale_rejected_and_missing_reviews_fail_closed(self):
        stale_target = case(id="hp1-001")
        rejected_target = case(id="hp1-002", question="Q2?")
        missing_target = case(id="hp1-003", question="Q3?")
        stale = review(stale_target, case_content_sha256="0" * 64)
        rejected = review(rejected_target, decision="rejected")
        approved, errors = materialize_approved_cases(
            [stale_target, rejected_target, missing_target],
            [(1, stale), (2, rejected)],
        )
        self.assertEqual(approved, [])
        self.assertTrue(any("stale" in error for error in errors))
        self.assertTrue(any("not approved" in error for error in errors))
        self.assertTrue(any("missing human review" in error for error in errors))

    def test_corpus_change_invalidates_prior_approval(self):
        target = case()
        approved, errors = materialize_approved_cases(
            [target], [(1, review(target))], expected_corpus_sha256="b" * 64
        )
        self.assertEqual(approved, [])
        self.assertTrue(any("corpus index changed" in error for error in errors))

    def test_materialized_formal_case_is_bound_to_content_and_corpus(self):
        target = case()
        approved, errors = materialize_approved_cases(
            [target], [(1, review(target))], expected_corpus_sha256="a" * 64
        )
        self.assertEqual(errors, [])
        self.assertEqual(validate_materialized_reviews(approved, "a" * 64), [])
        tampered = [{**approved[0], "reference_answer": "Tampered."}]
        self.assertTrue(
            any(
                "does not match case" in error
                for error in validate_materialized_reviews(tampered, "a" * 64)
            )
        )

    def test_materialized_gold_chunk_must_exist_in_bound_corpus(self):
        target = case()
        approved, errors = materialize_approved_cases(
            [target], [(1, review(target))], expected_corpus_sha256="a" * 64
        )
        self.assertEqual(errors, [])
        validation_errors = validate_materialized_reviews(
            approved, "a" * 64, {"c" * 64}
        )
        self.assertTrue(any("absent from current corpus" in error for error in validation_errors))
        self.assertTrue(
            any(
                "corpus hash is stale" in error
                for error in validate_materialized_reviews(approved, "b" * 64)
            )
        )

    def test_invalid_review_schema_is_rejected(self):
        errors = validate_review_records(
            [(1, {"case_id": "hp1-001", "decision": "maybe"})]
        )
        self.assertTrue(any("missing fields" in error for error in errors))

    def test_progress_separates_current_stale_rejected_and_missing_reviews(self):
        approved = case(id="hp1-001", category="single_hop")
        missing = case(id="hp1-002", category="adversarial", answerable=False, evidence=[])
        stale_case = case(id="hp1-003", category="multi_hop")
        stale_corpus = case(id="hp1-004", category="reasoning")
        rejected = case(id="hp1-005", category="single_hop")
        invalid = case(id="hp1-006", category="unanswerable", answerable=False, evidence=[])
        records = [
            (1, review(approved)),
            (2, review(stale_case, case_content_sha256="0" * 64)),
            (3, review(stale_corpus, corpus_index_sha256="c" * 64)),
            (4, review(rejected, decision="rejected")),
            (5, review(invalid, gold_evidence_chunk_sha256=["b" * 64])),
            (6, review(case(id="orphan"))),
        ]
        report = review_progress(
            [approved, missing, stale_case, stale_corpus, rejected, invalid],
            records,
            "a" * 64,
            next_limit=4,
        )
        self.assertEqual(report["approved_cases"], 1)
        self.assertEqual(report["remaining_cases"], 5)
        self.assertEqual(report["status_counts"]["missing"], 1)
        self.assertEqual(report["status_counts"]["stale_case"], 1)
        self.assertEqual(report["status_counts"]["stale_corpus"], 1)
        self.assertEqual(report["status_counts"]["rejected"], 1)
        self.assertEqual(report["status_counts"]["invalid_approval"], 1)
        self.assertEqual(report["next_review_ids"][0], "hp1-002")
        self.assertEqual(report["orphan_review_ids"], ["orphan"])
        self.assertFalse(report["ready_for_formal"])


if __name__ == "__main__":
    unittest.main()
