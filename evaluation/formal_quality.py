"""Pre-registered, machine-readable release checks for a formal benchmark."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

FORMAL_QUALITY_PROTOCOL = {
    "id": "formal-quality-2026-09-16.1",
    "minimum_unique_cases": 50,
    "minimum_repetitions": 3,
    "minimum_bootstrap_samples": 2000,
    "required_chat_model": "qwen3.7-flash",
    "required_judge_model": "deepseek-v4-pro-0813",
    "maximum_error_rate_each_system": 0.05,
    "maximum_secret_leak_rate_each_system": 0.0,
    "agentic_minimums": {
        "answer_hit": 0.80,
        "answerability_decision_accuracy": 0.90,
        "citation_evidence_recall": 0.80,
        "citation_precision": 0.75,
        "judge_correctness": 0.80,
        "judge_relevance": 0.85,
        "judge_faithfulness": 0.85,
        "claim_citation_contract_pass_rate": 1.0,
    },
    "agentic_maximums": {
        "claim_citation_validation_failure_rate": 0.02,
        "grounding_failure_rate": 0.10,
        "secret_leak_rate": 0.0,
    },
    "agentic_stability_minimums": {
        "all_runs_execution_success_rate": 0.95,
        "termination_consistency_rate": 0.90,
        "answerability_consistency_rate": 0.90,
    },
    "agentic_vs_naive": {
        "primary_metrics": [
            "answer_hit", "judge_correctness", "judge_faithfulness"
        ],
        "minimum_favored_metrics": 1,
        "minimum_effect_size": 0.03,
        "allow_significant_regressions": False,
    },
}


def _check(checks, check_id, passed, actual, expected):
    checks.append({
        "id": check_id,
        "passed": bool(passed),
        "actual": actual,
        "expected": expected,
    })


def _comparison(summary, metric):
    comparisons = summary.get("_pairwise_comparisons", {}).get("comparisons", [])
    for item in comparisons:
        if item.get("metric") != metric:
            continue
        if {item.get("system_a"), item.get("system_b")} == {
            "naive-rag", "agentic-rag"
        }:
            return item
    return None


def _agentic_minus_naive(comparison):
    if not comparison or comparison.get("mean_delta_a_minus_b") is None:
        return None
    delta = float(comparison["mean_delta_a_minus_b"])
    return delta if comparison.get("system_a") == "agentic-rag" else -delta


def _is_sha256(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value.lower())
    )


def evaluate_formal_quality(summary, details_path: Path | None = None):
    """Evaluate a saved summary without changing thresholds after results exist."""
    protocol = FORMAL_QUALITY_PROTOCOL
    metadata = summary.get("_metadata", {})
    checks = []
    _check(checks, "formal_mode", metadata.get("formal_benchmark") is True,
           metadata.get("formal_benchmark"), True)
    _check(checks, "judge_enabled", metadata.get("judge_enabled") is True,
           metadata.get("judge_enabled"), True)
    _check(
        checks, "protocol_version",
        metadata.get("formal_quality_protocol") == protocol["id"],
        metadata.get("formal_quality_protocol"), protocol["id"],
    )
    _check(
        checks, "chat_model",
        metadata.get("chat_model") == protocol["required_chat_model"],
        metadata.get("chat_model"), protocol["required_chat_model"],
    )
    _check(
        checks, "judge_model",
        metadata.get("judge_model") == protocol["required_judge_model"],
        metadata.get("judge_model"), protocol["required_judge_model"],
    )
    _check(
        checks, "dataset_sha256", _is_sha256(metadata.get("dataset_sha256")),
        metadata.get("dataset_sha256"), "64-character SHA256 hex digest",
    )
    repetitions = metadata.get("repetitions")
    _check(
        checks, "minimum_repetitions",
        isinstance(repetitions, int)
        and repetitions >= protocol["minimum_repetitions"],
        repetitions, f">={protocol['minimum_repetitions']}",
    )
    bootstrap_samples = metadata.get("bootstrap_samples")
    _check(
        checks, "minimum_bootstrap_samples",
        isinstance(bootstrap_samples, int)
        and bootstrap_samples >= protocol["minimum_bootstrap_samples"],
        bootstrap_samples, f">={protocol['minimum_bootstrap_samples']}",
    )

    expected_systems = {"direct", "naive-rag", "agentic-rag"}
    actual_systems = expected_systems & summary.keys()
    _check(checks, "all_systems", actual_systems == expected_systems,
           sorted(actual_systems), sorted(expected_systems))
    for system in sorted(expected_systems):
        values = summary.get(system, {})
        unique_cases = values.get("unique_cases")
        _check(
            checks, f"{system}.minimum_unique_cases",
            isinstance(unique_cases, int)
            and unique_cases >= protocol["minimum_unique_cases"],
            unique_cases, f">={protocol['minimum_unique_cases']}",
        )
        error_rate = values.get("error_rate")
        _check(
            checks, f"{system}.maximum_error_rate",
            isinstance(error_rate, (int, float))
            and error_rate <= protocol["maximum_error_rate_each_system"],
            error_rate, f"<={protocol['maximum_error_rate_each_system']}",
        )
        leak_rate = values.get("secret_leak_rate")
        _check(
            checks, f"{system}.maximum_secret_leak_rate",
            isinstance(leak_rate, (int, float))
            and leak_rate <= protocol["maximum_secret_leak_rate_each_system"],
            leak_rate, f"<={protocol['maximum_secret_leak_rate_each_system']}",
        )
    expected_records = sum(
        int(summary.get(system, {}).get("cases", 0)) for system in expected_systems
    )
    _check(
        checks, "detail_record_count",
        metadata.get("detail_records") == expected_records,
        metadata.get("detail_records"), expected_records,
    )

    agentic = summary.get("agentic-rag", {})
    for metric, threshold in protocol["agentic_minimums"].items():
        value = agentic.get(metric)
        _check(
            checks, f"agentic-rag.{metric}",
            isinstance(value, (int, float)) and value >= threshold,
            value, f">={threshold}",
        )
    for metric, threshold in protocol["agentic_maximums"].items():
        value = agentic.get(metric)
        _check(
            checks, f"agentic-rag.{metric}",
            isinstance(value, (int, float)) and value <= threshold,
            value, f"<={threshold}",
        )
    stability = agentic.get("repeat_stability", {})
    _check(
        checks, "agentic-rag.repeat_stability.minimum_repeated_cases",
        isinstance(stability.get("repeated_cases"), int)
        and stability["repeated_cases"] >= protocol["minimum_unique_cases"],
        stability.get("repeated_cases"), f">={protocol['minimum_unique_cases']}",
    )
    for metric, threshold in protocol["agentic_stability_minimums"].items():
        value = stability.get(metric)
        _check(
            checks, f"agentic-rag.repeat_stability.{metric}",
            isinstance(value, (int, float)) and value >= threshold,
            value, f">={threshold}",
        )

    comparison_protocol = protocol["agentic_vs_naive"]
    favored = 0
    regressions = []
    effects = {}
    for metric in comparison_protocol["primary_metrics"]:
        comparison = _comparison(summary, metric)
        effect = _agentic_minus_naive(comparison)
        effects[metric] = effect
        inference = comparison.get("inference") if comparison else None
        if (
            inference == "agentic-rag_favored"
            and effect is not None
            and effect >= comparison_protocol["minimum_effect_size"]
            and comparison.get("paired_cases", 0) >= protocol["minimum_unique_cases"]
        ):
            favored += 1
        if inference == "naive-rag_favored":
            regressions.append(metric)
    _check(
        checks, "agentic_vs_naive.minimum_favored_primary_metrics",
        favored >= comparison_protocol["minimum_favored_metrics"],
        {"favored": favored, "effects": effects},
        {
            "favored": f">={comparison_protocol['minimum_favored_metrics']}",
            "minimum_effect_size": comparison_protocol["minimum_effect_size"],
        },
    )
    _check(
        checks, "agentic_vs_naive.no_significant_primary_regression",
        not regressions, regressions, [],
    )

    if details_path is not None:
        expected_hash = metadata.get("details_sha256")
        actual_hash = (
            sha256(details_path.read_bytes()).hexdigest()
            if details_path.is_file() else None
        )
        _check(
            checks, "details_sha256", actual_hash == expected_hash,
            actual_hash, expected_hash,
        )

    failed = [item["id"] for item in checks if not item["passed"]]
    return {
        "protocol": protocol,
        "passed": not failed,
        "failed_checks": failed,
        "checks": checks,
    }
