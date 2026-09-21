"""Audit pre-registered risk coverage across seed and candidate evaluation pools."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.audit_dataset import normalize, read_cases, validate_cases

PROTOCOL_VERSION = "risk-coverage-2026-09-14.1"
DEFAULT_DATASETS = (
    PROJECT_ROOT / "evaluation" / "dataset.jsonl",
    PROJECT_ROOT / "evaluation" / "dataset_candidates.jsonl",
)
MINIMUM_CATEGORY_CASES = {
    "single_hop": 20,
    "reasoning": 10,
    "multi_hop": 11,
    "unanswerable": 5,
    "adversarial": 6,
}
MINIMUM_RISK_CASES = {
    "knowledge_absence": 5,
    "false_premise": 4,
    "prompt_injection": 1,
    "secret_exfiltration": 1,
    "belief_fact_conflict": 1,
    "multi_source_disambiguation": 1,
    "underspecified_query": 1,
    "clarification_required": 1,
}


def summarize_coverage(cases, category_minimums, risk_minimums) -> dict:
    category_counts = Counter(case.get("category") for case in cases)
    risk_counts = Counter(
        tag for case in cases for tag in set(case.get("risk_tags") or [])
    )
    checks = []
    for category, minimum in category_minimums.items():
        actual = category_counts[category]
        checks.append({
            "kind": "category",
            "name": category,
            "actual": actual,
            "minimum": minimum,
            "passed": actual >= minimum,
        })
    for risk, minimum in risk_minimums.items():
        actual = risk_counts[risk]
        checks.append({
            "kind": "risk",
            "name": risk,
            "actual": actual,
            "minimum": minimum,
            "passed": actual >= minimum,
        })
    return {
        "category_counts": dict(sorted(category_counts.items())),
        "risk_case_counts": dict(sorted(risk_counts.items())),
        "checks": checks,
        "passed": all(check["passed"] for check in checks),
    }


def audit_datasets(paths, category_minimums=None, risk_minimums=None) -> dict:
    paths = [Path(path).resolve() for path in paths]
    errors = []
    all_cases = []
    dataset_records = []
    seen_ids = set()
    seen_questions = set()
    for path in paths:
        numbered, parse_errors = read_cases(path)
        validation_errors, warnings = validate_cases(numbered)
        errors.extend(f"{path.name}: {error}" for error in parse_errors)
        errors.extend(f"{path.name}: {error}" for error in validation_errors)
        cases = [case for _, case in numbered]
        for case in cases:
            case_id = case.get("id")
            question = normalize(case.get("question", ""))
            if case_id in seen_ids:
                errors.append(f"cross-dataset duplicate id: {case_id}")
            if question and question in seen_questions:
                errors.append(f"cross-dataset duplicate question: {case_id}")
            seen_ids.add(case_id)
            seen_questions.add(question)
        all_cases.extend(cases)
        dataset_records.append({
            "path": str(path),
            "sha256": sha256(path.read_bytes()).hexdigest(),
            "cases": len(cases),
            "warnings": warnings,
        })
    coverage = summarize_coverage(
        all_cases,
        category_minimums or MINIMUM_CATEGORY_CASES,
        risk_minimums or MINIMUM_RISK_CASES,
    )
    errors.extend(
        f"coverage below minimum: {check['kind']} {check['name']} "
        f"{check['actual']} < {check['minimum']}"
        for check in coverage["checks"]
        if not check["passed"]
    )
    return {
        "protocol_version": PROTOCOL_VERSION,
        "datasets": dataset_records,
        "total_cases": len(all_cases),
        "human_approved_cases": sum(
            case.get("review_status") == "human_approved" for case in all_cases
        ),
        **coverage,
        "errors": errors,
        "valid": not errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, action="append", dest="datasets")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_datasets(args.datasets or DEFAULT_DATASETS)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
