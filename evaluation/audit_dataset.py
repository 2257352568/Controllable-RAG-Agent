"""Validate evaluation-case structure and optionally verify evidence against local FAISS text.

The FAISS pickle must only be loaded when it was created locally or otherwise trusted.
This command never treats absence from one corpus snapshot as proof that a question is
unanswerable; negative cases still require human review.
"""

import argparse
import json
import pickle
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = Path(__file__).with_name("dataset.jsonl")
DEFAULT_CORPUS = PROJECT_ROOT / "chunks_vector_store" / "index.pkl"
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*-\d{3}$")
TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
ALLOWED_CATEGORIES = {
    "single_hop",
    "reasoning",
    "multi_hop",
    "unanswerable",
    "adversarial",
}
ALLOWED_REVIEW_STATUSES = {"needs_human_review", "source_verified", "human_approved"}
ALLOWED_RISK_TAGS = {
    "belief_fact_conflict",
    "clarification_required",
    "false_premise",
    "knowledge_absence",
    "multi_source_disambiguation",
    "prompt_injection",
    "secret_exfiltration",
    "underspecified_query",
}
REQUIRED_FIELDS = {
    "id",
    "category",
    "question",
    "reference_answer",
    "acceptable_answers",
    "evidence",
    "answerable",
}


def normalize(text):
    return " ".join(TOKEN_PATTERN.findall(str(text).lower().replace("¾", " 3/4 ")))


def read_cases(path):
    cases = []
    parse_errors = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                cases.append((line_number, json.loads(line)))
            except json.JSONDecodeError as error:
                parse_errors.append(f"line {line_number}: invalid JSON: {error.msg}")
    return cases, parse_errors


def validate_cases(numbered_cases, require_human_approved=False):
    errors = []
    warnings = []
    seen_ids = set()
    seen_questions = set()

    for line_number, case in numbered_cases:
        label = case.get("id", f"line {line_number}")
        missing = sorted(REQUIRED_FIELDS - case.keys())
        if missing:
            errors.append(f"{label}: missing fields: {', '.join(missing)}")
            continue
        if not isinstance(case["id"], str) or not ID_PATTERN.fullmatch(case["id"]):
            errors.append(f"{label}: id must match {ID_PATTERN.pattern}")
        if case["id"] in seen_ids:
            errors.append(f"{label}: duplicate id")
        seen_ids.add(case["id"])

        normalized_question = normalize(case["question"])
        if not normalized_question:
            errors.append(f"{label}: question must not be empty")
        if normalized_question in seen_questions:
            errors.append(f"{label}: duplicate normalized question")
        seen_questions.add(normalized_question)

        if case["category"] not in ALLOWED_CATEGORIES:
            errors.append(f"{label}: unsupported category {case['category']!r}")
        if not isinstance(case["answerable"], bool):
            errors.append(f"{label}: answerable must be a JSON boolean")
        for field in ("acceptable_answers", "evidence"):
            value = case[field]
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not normalize(item) for item in value
            ):
                errors.append(f"{label}: {field} must be a list of non-empty strings")
        answer_groups = case.get("acceptable_answer_groups")
        if answer_groups is not None and (
            not isinstance(answer_groups, list)
            or not answer_groups
            or any(
                not isinstance(group, list)
                or not group
                or any(not isinstance(item, str) or not normalize(item) for item in group)
                for group in answer_groups
            )
        ):
            errors.append(
                f"{label}: acceptable_answer_groups must be a non-empty list of non-empty string lists"
            )
        if isinstance(case["acceptable_answers"], list) and not case["acceptable_answers"]:
            errors.append(f"{label}: acceptable_answers must not be empty")
        if case["answerable"] and not case["evidence"]:
            errors.append(f"{label}: answerable case must include evidence markers")
        if not case["answerable"] and case["evidence"]:
            errors.append(f"{label}: unanswerable case must not claim positive evidence")
        review_search_terms = case.get("review_search_terms")
        if not case["answerable"] and (
            not isinstance(review_search_terms, list)
            or not review_search_terms
            or any(
                not isinstance(item, str) or not normalize(item)
                for item in review_search_terms
            )
        ):
            errors.append(
                f"{label}: negative case requires non-empty review_search_terms"
            )
        if case["answerable"] and review_search_terms is not None:
            errors.append(f"{label}: positive case must not define review_search_terms")

        risk_tags = case.get("risk_tags", [])
        if (
            not isinstance(risk_tags, list)
            or any(not isinstance(tag, str) or tag not in ALLOWED_RISK_TAGS for tag in risk_tags)
            or len(risk_tags) != len(set(risk_tags))
        ):
            errors.append(f"{label}: risk_tags must be a unique list of allowed values")
        elif case["category"] in {"unanswerable", "adversarial"} and not risk_tags:
            errors.append(f"{label}: negative/adversarial case requires risk_tags")

        review_status = case.get("review_status", "needs_human_review")
        if review_status not in ALLOWED_REVIEW_STATUSES:
            errors.append(f"{label}: unsupported review_status {review_status!r}")
        if require_human_approved and review_status != "human_approved":
            errors.append(f"{label}: formal benchmark requires review_status=human_approved")
        elif "review_status" not in case:
            warnings.append(f"{label}: review_status missing; treated as needs_human_review")

    return errors, warnings


def load_trusted_corpus(index_path):
    """Load text from a trusted LangChain FAISS pickle without requiring an API key."""
    with index_path.open("rb") as stream:
        docstore, _ = pickle.load(stream)  # noqa: S301 - explicit trusted-local-only command
    documents = list(docstore._dict.values())
    return [
        {
            "text": normalize(document.page_content),
            "page": document.metadata.get("page"),
            "content_sha256": sha256(
                str(document.page_content).encode("utf-8", errors="replace")
            ).hexdigest(),
        }
        for document in documents
    ]


def verify_evidence(numbered_cases, corpus_documents):
    errors = []
    matches = {}
    for _, case in numbered_cases:
        if not case.get("answerable"):
            continue
        case_matches = []
        for marker in case.get("evidence", []):
            normalized_marker = normalize(marker)
            pages = sorted(
                {
                    document["page"]
                    for document in corpus_documents
                    if normalized_marker in document["text"] and document["page"] is not None
                }
            )
            if not pages:
                errors.append(f"{case['id']}: evidence marker not found in corpus: {marker!r}")
            case_matches.append({"marker": marker, "pages": pages})
        matches[case["id"]] = case_matches
    return errors, matches


def build_report(path, numbered_cases, errors, warnings, evidence_matches=None, corpus_path=None):
    cases = [case for _, case in numbered_cases]
    return {
        "dataset": str(path.resolve()),
        "dataset_sha256": sha256(path.read_bytes()).hexdigest(),
        "case_count": len(cases),
        "category_counts": dict(sorted(Counter(case.get("category") for case in cases).items())),
        "review_status_counts": dict(
            sorted(Counter(case.get("review_status", "needs_human_review") for case in cases).items())
        ),
        "corpus": str(corpus_path.resolve()) if corpus_path else None,
        "corpus_sha256": sha256(corpus_path.read_bytes()).hexdigest() if corpus_path else None,
        "evidence_matches": evidence_matches,
        "errors": errors,
        "warnings": warnings,
        "valid": not errors,
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--trusted-corpus-index",
        type=Path,
        help="Verify evidence against a trusted local LangChain FAISS index.pkl.",
    )
    parser.add_argument("--min-cases", type=int, default=1)
    parser.add_argument("--require-human-approved", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    numbered_cases, parse_errors = read_cases(args.dataset)
    errors, warnings = validate_cases(numbered_cases, args.require_human_approved)
    errors = [*parse_errors, *errors]
    if len(numbered_cases) < args.min_cases:
        errors.append(f"dataset has {len(numbered_cases)} cases; minimum is {args.min_cases}")

    evidence_matches = None
    if args.trusted_corpus_index:
        corpus = load_trusted_corpus(args.trusted_corpus_index)
        evidence_errors, evidence_matches = verify_evidence(numbered_cases, corpus)
        errors.extend(evidence_errors)
    if any(not case.get("answerable", True) for _, case in numbered_cases):
        warnings.append(
            "Unanswerable/adversarial cases require human review; corpus search cannot prove absence."
        )

    report = build_report(
        args.dataset,
        numbered_cases,
        errors,
        warnings,
        evidence_matches,
        args.trusted_corpus_index,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
