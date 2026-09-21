"""Verify a formal benchmark summary against the pre-registered release gate."""

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.formal_quality import evaluate_formal_quality  # noqa: E402
from evaluation.run_evaluation import (  # noqa: E402
    SYSTEMS,
    build_pairwise_comparisons,
    build_summary,
)


def _canonical_digest(value):
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def _append_check(report, check_id, passed, actual, expected):
    check = {
        "id": check_id,
        "passed": bool(passed),
        "actual": actual,
        "expected": expected,
    }
    report["checks"].insert(0, check)
    if not passed:
        report["failed_checks"].insert(0, check_id)
        report["passed"] = False


def _read_jsonl(path):
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("JSONL records must be objects")
    return records


def _check_dataset_binding(report, summary, records, dataset_path):
    metadata = summary.get("_metadata", {})
    dataset_bytes = dataset_path.read_bytes()
    actual_hash = sha256(dataset_bytes).hexdigest()
    _append_check(
        report,
        "dataset_sha256_matches_file",
        actual_hash == metadata.get("dataset_sha256"),
        actual_hash,
        metadata.get("dataset_sha256"),
    )
    cases = _read_jsonl(dataset_path)
    case_by_id = {str(case.get("id")): case for case in cases}
    unique_case_ids = len(case_by_id) == len(cases) and "None" not in case_by_id
    _append_check(
        report, "dataset_case_ids_unique", unique_case_ids,
        len(case_by_id), len(cases),
    )
    repetitions = metadata.get("repetitions")
    expected_keys = {
        (case_id, system, repeat_index)
        for case_id in case_by_id
        for system in SYSTEMS
        for repeat_index in range(1, repetitions + 1)
    } if isinstance(repetitions, int) and repetitions > 0 else set()
    actual_keys = [
        (
            str(record.get("case_id")),
            record.get("system"),
            record.get("repeat_index", 1),
        )
        for record in records
    ]
    key_contract = len(actual_keys) == len(set(actual_keys)) and set(actual_keys) == expected_keys
    _append_check(
        report, "details_complete_case_system_repetition_product", key_contract,
        {"records": len(actual_keys), "unique_keys": len(set(actual_keys))},
        {"records": len(expected_keys), "unique_keys": len(expected_keys)},
    )
    field_contract = all(
        record.get("case_id") in case_by_id
        and all(
            record.get(field) == case_by_id[record["case_id"]].get(field)
            for field in ("category", "question", "reference_answer", "answerable")
        )
        for record in records
    )
    _append_check(
        report, "details_case_fields_match_dataset", field_contract,
        field_contract, True,
    )


def verify_saved_formal_result(summary, records, details_path, dataset_path):
    """Recompute aggregates from details before applying the release protocol."""
    metadata = summary.get("_metadata", {})
    samples = metadata.get("bootstrap_samples")
    if not isinstance(samples, int) or samples <= 0:
        samples = 1
    seed = metadata.get("bootstrap_seed")
    if not isinstance(seed, int):
        seed = 0
    rebuilt = build_summary(records)
    rebuilt["_pairwise_comparisons"] = build_pairwise_comparisons(
        records,
        samples=samples,
        seed=seed,
    )
    saved_aggregates = {
        key: summary.get(key)
        for key in (*SYSTEMS, "_pairwise_comparisons")
    }
    rebuilt_aggregates = {
        key: rebuilt.get(key)
        for key in (*SYSTEMS, "_pairwise_comparisons")
    }
    summary_matches = saved_aggregates == rebuilt_aggregates
    rebuilt["_metadata"] = metadata
    report = evaluate_formal_quality(rebuilt, details_path)
    _append_check(
        report, "summary_matches_recomputed_details", summary_matches,
        _canonical_digest(saved_aggregates),
        _canonical_digest(rebuilt_aggregates),
    )
    _check_dataset_binding(report, summary, records, dataset_path)
    return report


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--details", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        summary = json.loads(args.summary.read_text(encoding="utf-8"))
        records = _read_jsonl(args.details)
        if not isinstance(summary, dict) or not all(
            isinstance(record, dict) for record in records
        ):
            raise ValueError("summary and detail records must be JSON objects")
        report = verify_saved_formal_result(
            summary, records, args.details, args.dataset
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        report = {
            "passed": False,
            "failed_checks": ["result_parse_or_recompute_failed"],
            "error_type": type(error).__name__,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
