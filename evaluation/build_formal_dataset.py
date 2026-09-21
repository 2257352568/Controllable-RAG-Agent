"""Materialize a formal benchmark from hash-bound human approval records."""

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.audit_dataset import read_cases, validate_cases  # noqa: E402
from evaluation.review_workflow import (  # noqa: E402
    materialize_approved_cases,
    read_review_records,
)


def load_cases(path):
    numbered_cases, parse_errors = read_cases(path)
    validation_errors, _ = validate_cases(numbered_cases)
    errors = [*parse_errors, *validation_errors]
    if errors:
        raise ValueError(f"{path}:\n- " + "\n- ".join(errors))
    return [case for _, case in numbered_cases]


def merge_cases(case_sets):
    cases = [case for case_set in case_sets for case in case_set]
    numbered_cases = list(enumerate(cases, start=1))
    errors, _ = validate_cases(numbered_cases)
    if errors:
        raise ValueError("Merged dataset is invalid:\n- " + "\n- ".join(errors))
    if len(cases) < 50:
        raise ValueError(f"Merged dataset has {len(cases)} cases; at least 50 are required")
    return sorted(cases, key=lambda case: case["id"])


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reviews",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "reviews.jsonl",
        help="Append-only decisions produced by review_dataset.py.",
    )
    parser.add_argument(
        "--trusted-corpus-index",
        type=Path,
        default=PROJECT_ROOT / "chunks_vector_store" / "index.pkl",
        help="Current corpus snapshot hash must match every approval record.",
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        type=Path,
        default=[
            PROJECT_ROOT / "evaluation" / "dataset.jsonl",
            PROJECT_ROOT / "evaluation" / "dataset_candidates.jsonl",
        ],
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "dataset_formal.jsonl",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.output.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite existing file: {args.output}")
    try:
        cases = merge_cases([load_cases(path) for path in args.inputs])
        review_records, review_parse_errors = read_review_records(args.reviews)
        if review_parse_errors:
            raise ValueError("Invalid review log:\n- " + "\n- ".join(review_parse_errors))
        if not args.trusted_corpus_index.is_file():
            raise ValueError(f"Missing corpus index: {args.trusted_corpus_index}")
        corpus_sha256 = sha256(args.trusted_corpus_index.read_bytes()).hexdigest()
        cases, review_errors = materialize_approved_cases(
            cases, review_records, expected_corpus_sha256=corpus_sha256
        )
        if review_errors:
            raise ValueError("Human review gate failed:\n- " + "\n- ".join(review_errors))
        if len(cases) < 50:
            raise ValueError(
                f"Formal dataset has {len(cases)} approved cases; at least 50 are required"
            )
        validation_errors, _ = validate_cases(
            list(enumerate(cases, 1)), require_human_approved=True
        )
        if validation_errors:
            raise ValueError(
                "Materialized formal dataset is invalid:\n- "
                + "\n- ".join(validation_errors)
            )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases),
        encoding="utf-8",
    )
    print(f"Wrote {len(cases)} approved cases to {args.output}")


if __name__ == "__main__":
    main()
