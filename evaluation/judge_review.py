"""Deterministic sampling and provenance validation for human judge audits."""

import json
import math
import statistics
from collections import defaultdict
from hashlib import sha256

JUDGE_REVIEW_VERSION = "2026-09-12.1"
JUDGE_METRICS = ("correctness", "relevance", "faithfulness")
AUDIT_PROTOCOL = {
    "id": "judge-audit-2026-09-12.1",
    "sampling_rate": 0.2,
    "sampling_seed": 20260912,
    "score_tolerance": 0.2,
    "minimum_agreement_within_tolerance": 0.8,
    "maximum_mean_absolute_error": 0.2,
    "required_review_coverage": 1.0,
}


def record_key(record):
    return f"{record.get('case_id')}|{record.get('system')}|{record.get('repeat_index', 1)}"


def record_sha256(record):
    payload = {
        "case_id": record.get("case_id"),
        "system": record.get("system"),
        "repeat_index": record.get("repeat_index", 1),
        "question": record.get("question"),
        "reference_answer": record.get("reference_answer"),
        "answer": record.get("answer"),
        "judge_context_audit_evidence": record.get("judge_context_audit_evidence", []),
        "judge": record.get("judge"),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def select_audit_records(records, rate=0.2, seed=20260912):
    """Select at least rate from each system/category stratum via stable hash ranking."""
    if not 0 < rate <= 1:
        raise ValueError("audit rate must be in (0, 1]")
    strata = defaultdict(list)
    for record in records:
        if record.get("error") or not isinstance(record.get("judge"), dict):
            continue
        strata[(record.get("system"), record.get("category"))].append(record)
    selected = []
    for stratum in sorted(strata, key=lambda item: tuple(str(value) for value in item)):
        candidates = strata[stratum]
        count = max(1, math.ceil(len(candidates) * rate))
        ranked = sorted(
            candidates,
            key=lambda record: sha256(
                f"{seed}:{record_key(record)}".encode("utf-8")
            ).hexdigest(),
        )
        selected.extend(ranked[:count])
    return sorted(selected, key=record_key)


def validate_review(review):
    required = {
        "record_key", "record_sha256", "details_sha256", "reviewer",
        "reviewed_at", "review_version", "human_scores",
    }
    missing = sorted(required - review.keys())
    if missing:
        return ["missing fields: " + ", ".join(missing)]
    errors = []
    if review["review_version"] != JUDGE_REVIEW_VERSION:
        errors.append("stale review_version")
    for field in ("record_sha256", "details_sha256"):
        value = review[field]
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value.lower())
        ):
            errors.append(f"{field} must be a SHA256 hex digest")
    if not str(review["reviewer"]).strip():
        errors.append("reviewer must not be empty")
    scores = review["human_scores"]
    if not isinstance(scores, dict):
        errors.append("human_scores must be an object")
    else:
        missing_scores = sorted({"correctness", "relevance"} - scores.keys())
        if missing_scores:
            errors.append("human_scores missing: " + ", ".join(missing_scores))
        for metric, value in scores.items():
            if metric not in JUDGE_METRICS or type(value) not in (int, float) or not 0 <= value <= 1:
                errors.append(f"invalid human score for {metric}")
    return errors


def build_audit_report(records, selected, reviews, details_sha256, tolerance=0.2):
    if not 0 <= tolerance <= 1:
        raise ValueError("tolerance must be in [0, 1]")
    latest = {}
    invalid_reviews = []
    for line_number, review in reviews:
        errors = validate_review(review)
        if errors:
            invalid_reviews.extend(f"line {line_number}: {error}" for error in errors)
            continue
        latest[review["record_key"]] = review

    metric_differences = defaultdict(list)
    stale = []
    reviewed = 0
    for record in selected:
        key = record_key(record)
        review = latest.get(key)
        if review is None:
            continue
        if review["details_sha256"] != details_sha256 or review["record_sha256"] != record_sha256(record):
            stale.append(key)
            continue
        reviewed += 1
        for metric, human_value in review["human_scores"].items():
            judge_value = record["judge"].get(metric)
            if judge_value is not None:
                metric_differences[metric].append(abs(float(judge_value) - float(human_value)))

    metrics = {}
    required_metrics = {
        metric
        for record in selected
        for metric in JUDGE_METRICS
        if record.get("judge", {}).get(metric) is not None
    }
    for metric in JUDGE_METRICS:
        differences = metric_differences[metric]
        mean_absolute_error = (
            round(statistics.fmean(differences), 4) if differences else None
        )
        agreement = round(
            sum(value <= tolerance for value in differences) / len(differences), 4
        ) if differences else None
        metrics[metric] = {
            "comparisons": len(differences),
            "mean_absolute_error": mean_absolute_error,
            "agreement_within_tolerance": agreement,
            "required": metric in required_metrics,
            "quality_gate_passed": (
                metric not in required_metrics
                or (
                    mean_absolute_error is not None
                    and mean_absolute_error <= AUDIT_PROTOCOL["maximum_mean_absolute_error"]
                    and agreement is not None
                    and agreement >= AUDIT_PROTOCOL["minimum_agreement_within_tolerance"]
                )
            ),
        }
    eligible_records = sum(
        not record.get("error") and isinstance(record.get("judge"), dict)
        for record in records
    )
    effective_selection_rate = (
        round(len(selected) / eligible_records, 4) if eligible_records else None
    )
    review_coverage = round(reviewed / len(selected), 4) if selected else None
    complete = bool(selected) and reviewed == len(selected) and not invalid_reviews and not stale
    quality_gate_passed = (
        complete
        and effective_selection_rate is not None
        and effective_selection_rate >= AUDIT_PROTOCOL["sampling_rate"]
        and review_coverage is not None
        and review_coverage >= AUDIT_PROTOCOL["required_review_coverage"]
        and tolerance == AUDIT_PROTOCOL["score_tolerance"]
        and all(metrics[metric]["quality_gate_passed"] for metric in required_metrics)
    )
    return {
        "protocol": AUDIT_PROTOCOL,
        "eligible_records": eligible_records,
        "selected_records": len(selected),
        "effective_selection_rate": effective_selection_rate,
        "reviewed_records": reviewed,
        "review_coverage": review_coverage,
        "complete": complete,
        "quality_gate_passed": quality_gate_passed,
        "tolerance": tolerance,
        "metrics": metrics,
        "stale_record_keys": stale,
        "invalid_reviews": invalid_reviews,
    }
