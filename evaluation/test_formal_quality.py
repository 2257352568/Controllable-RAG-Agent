import json
import unittest
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.formal_quality import (
    FORMAL_QUALITY_PROTOCOL,
    evaluate_formal_quality,
)
from evaluation.run_evaluation import build_pairwise_comparisons, build_summary
from evaluation.verify_formal_quality import verify_saved_formal_result


def passing_summary(details_bytes):
    common = {
        "cases": 150,
        "unique_cases": 50,
        "error_rate": 0.0,
        "secret_leak_rate": 0.0,
    }
    agentic = {
        **common,
        "answer_hit": 0.90,
        "answerability_decision_accuracy": 0.95,
        "citation_evidence_recall": 0.90,
        "citation_precision": 0.85,
        "judge_correctness": 0.90,
        "judge_relevance": 0.90,
        "judge_faithfulness": 0.90,
        "claim_citation_contract_pass_rate": 1.0,
        "claim_citation_validation_failure_rate": 0.0,
        "grounding_failure_rate": 0.05,
        "repeat_stability": {
            "repeated_cases": 50,
            "all_runs_execution_success_rate": 0.98,
            "termination_consistency_rate": 0.94,
            "answerability_consistency_rate": 0.94,
        },
    }
    comparisons = []
    for metric in ("answer_hit", "judge_correctness", "judge_faithfulness"):
        comparisons.append({
            "system_a": "naive-rag",
            "system_b": "agentic-rag",
            "metric": metric,
            "paired_cases": 50,
            "mean_delta_a_minus_b": -0.05,
            "inference": "agentic-rag_favored",
        })
    return {
        "direct": dict(common),
        "naive-rag": dict(common),
        "agentic-rag": agentic,
        "_pairwise_comparisons": {"comparisons": comparisons},
        "_metadata": {
            "formal_benchmark": True,
            "judge_enabled": True,
            "formal_quality_protocol": FORMAL_QUALITY_PROTOCOL["id"],
            "chat_model": "qwen3.7-flash",
            "judge_model": "deepseek-v4-pro-0813",
            "dataset_sha256": "a" * 64,
            "repetitions": 3,
            "bootstrap_samples": 2000,
            "detail_records": 450,
            "details_sha256": sha256(details_bytes).hexdigest(),
        },
    }


def passing_case_definitions():
    cases = []
    for case_number in range(52):
        if case_number < 20:
            category = "single_hop"
        elif case_number < 30:
            category = "reasoning"
        elif case_number < 41:
            category = "multi_hop"
        elif case_number < 46:
            category = "unanswerable"
        else:
            category = "adversarial"
        risk_tags = []
        if case_number == 30:
            risk_tags = ["belief_fact_conflict", "multi_source_disambiguation"]
        elif 41 <= case_number < 46:
            risk_tags = ["knowledge_absence"]
        elif 46 <= case_number < 50:
            risk_tags = ["false_premise"]
        elif case_number == 50:
            risk_tags = ["prompt_injection", "secret_exfiltration"]
        elif case_number == 51:
            risk_tags = ["underspecified_query", "clarification_required"]
        cases.append({
            "id": f"case-{case_number:03d}",
            "category": category,
            "question": f"Question {case_number}",
            "reference_answer": f"Answer {case_number}",
            "answerable": category not in {"unanswerable", "adversarial"},
            "risk_tags": risk_tags,
        })
    return cases


def passing_records():
    records = []
    scores = {"direct": 0.7, "naive-rag": 0.8, "agentic-rag": 1.0}
    for case in passing_case_definitions():
        for repeat_index in range(1, 4):
            for system, score in scores.items():
                is_agent = system == "agentic-rag"
                records.append({
                    "case_id": case["id"],
                    "repeat_index": repeat_index,
                    "system": system,
                    "category": case["category"],
                    "question": case["question"],
                    "reference_answer": case["reference_answer"],
                    "error": None,
                    "answerable": case["answerable"],
                    "abstained": not case["answerable"],
                    "answer_hit": score,
                    "answerability_decision_correct": 1.0,
                    "secret_leak_detected": False,
                    "token_f1": score,
                    "evidence_recall": score if system != "direct" else None,
                    "citation_evidence_recall": (
                        score if system != "direct" else None
                    ),
                    "citation_precision": score if system != "direct" else None,
                    "citation_count": 1 if system != "direct" else 0,
                    "claim_citation_coverage": 1.0 if is_agent else None,
                    "claim_citation_id_validity": 1.0 if is_agent else None,
                    "claim_citation_contract_pass": 1.0 if is_agent else None,
                    "claim_citation_validation_failed": 0.0 if is_agent else None,
                    "mean_evidence_ids_per_claim": 1.0 if is_agent else None,
                    "latency_seconds": 1.0,
                    "steps": 1,
                    "input_tokens": 10,
                    "output_tokens": 2,
                    "total_tokens": 12,
                    "model_requests": 1,
                    "embedding_requests": int(system != "direct"),
                    "embedding_inputs": int(system != "direct"),
                    "termination_reason": "answered",
                    "trace_events": [],
                    "judge": {
                        "correctness": score,
                        "relevance": score,
                        "faithfulness": score if system != "direct" else None,
                    },
                })
    return records


def passing_dataset():
    return "".join(
        json.dumps(case) + "\n"
        for case in passing_case_definitions()
    ).encode("utf-8")


def rebuilt_passing_summary(records, details_bytes, dataset_bytes):
    summary = build_summary(records)
    summary["_pairwise_comparisons"] = build_pairwise_comparisons(
        records, samples=2000, seed=20260912
    )
    summary["_metadata"] = {
        "formal_benchmark": True,
        "judge_enabled": True,
        "formal_quality_protocol": FORMAL_QUALITY_PROTOCOL["id"],
        "chat_model": "qwen3.7-flash",
        "judge_model": "deepseek-v4-pro-0813",
        "dataset_sha256": sha256(dataset_bytes).hexdigest(),
        "repetitions": 3,
        "bootstrap_samples": 2000,
        "bootstrap_seed": 20260912,
        "detail_records": len(records),
        "details_sha256": sha256(details_bytes).hexdigest(),
    }
    return summary


class FormalQualityTests(unittest.TestCase):
    def test_pre_registered_gate_passes_valid_result_and_fails_regression_or_tamper(self):
        details = b'{"record": 1}\n'
        with TemporaryDirectory() as directory:
            details_path = Path(directory) / "details.jsonl"
            details_path.write_bytes(details)
            summary = passing_summary(details)
            report = evaluate_formal_quality(summary, details_path)
            self.assertTrue(report["passed"])
            self.assertEqual(report["failed_checks"], [])

            failed = deepcopy(summary)
            failed["agentic-rag"]["answer_hit"] = 0.79
            failed["_pairwise_comparisons"]["comparisons"][0][
                "inference"
            ] = "naive-rag_favored"
            failed["_pairwise_comparisons"]["comparisons"][0][
                "mean_delta_a_minus_b"
            ] = 0.05
            details_path.write_text(json.dumps({"tampered": True}), encoding="utf-8")
            report = evaluate_formal_quality(failed, details_path)
            self.assertFalse(report["passed"])
            self.assertIn("agentic-rag.answer_hit", report["failed_checks"])
            self.assertIn(
                "agentic_vs_naive.no_significant_primary_regression",
                report["failed_checks"],
            )
            self.assertIn("details_sha256", report["failed_checks"])

        records = passing_records()
        dataset = passing_dataset()
        details = "".join(
            json.dumps(record, ensure_ascii=False) + "\n" for record in records
        ).encode("utf-8")
        with TemporaryDirectory() as directory:
            details_path = Path(directory) / "details.jsonl"
            dataset_path = Path(directory) / "dataset.jsonl"
            details_path.write_bytes(details)
            dataset_path.write_bytes(dataset)
            summary = rebuilt_passing_summary(records, details, dataset)
            report = verify_saved_formal_result(
                summary, records, details_path, dataset_path
            )
            self.assertTrue(report["passed"])

            tampered_summary = deepcopy(summary)
            tampered_summary["agentic-rag"]["answer_hit"] = 0.01
            report = verify_saved_formal_result(
                tampered_summary, records, details_path, dataset_path
            )
            self.assertFalse(report["passed"])
            self.assertIn(
                "summary_matches_recomputed_details", report["failed_checks"]
            )

            invalid_metadata = deepcopy(summary)
            invalid_metadata["_metadata"]["bootstrap_samples"] = 0
            report = verify_saved_formal_result(
                invalid_metadata, records, details_path, dataset_path
            )
            self.assertFalse(report["passed"])
            self.assertIn("minimum_bootstrap_samples", report["failed_checks"])

            dataset_path.write_text('{"id":"replacement"}\n', encoding="utf-8")
            report = verify_saved_formal_result(
                summary, records, details_path, dataset_path
            )
            self.assertFalse(report["passed"])
            self.assertIn("dataset_sha256_matches_file", report["failed_checks"])
            self.assertIn(
                "details_complete_case_system_repetition_product",
                report["failed_checks"],
            )


if __name__ == "__main__":
    unittest.main()
