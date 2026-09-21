"""Interactively review evaluation cases and append tamper-evident decisions."""

import argparse
import json
import pickle
import sys
from datetime import datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.audit_dataset import normalize, read_cases, validate_cases  # noqa: E402
from evaluation.review_workflow import (  # noqa: E402
    REVIEW_CHECKLIST_VERSION,
    case_content_sha256,
    latest_reviews,
    read_review_records,
    validate_review_records,
)

DEFAULT_INPUTS = [
    PROJECT_ROOT / "evaluation" / "dataset.jsonl",
    PROJECT_ROOT / "evaluation" / "dataset_candidates.jsonl",
]
DEFAULT_REVIEWS = PROJECT_ROOT / "evaluation" / "reviews.jsonl"
DEFAULT_INDEX = PROJECT_ROOT / "chunks_vector_store" / "index.pkl"


def load_cases(paths):
    cases = []
    source_by_id = {}
    errors = []
    for path in paths:
        numbered, parse_errors = read_cases(path)
        validation_errors, _ = validate_cases(numbered)
        errors.extend(f"{path}: {error}" for error in [*parse_errors, *validation_errors])
        for _, case in numbered:
            cases.append(case)
            source_by_id[case.get("id")] = {
                "path": str(path),
                "dataset_sha256": sha256(path.read_bytes()).hexdigest(),
            }
    if errors:
        raise ValueError("\n".join(errors))
    merged_errors, _ = validate_cases(list(enumerate(cases, 1)))
    if merged_errors:
        raise ValueError("Merged inputs are invalid:\n" + "\n".join(merged_errors))
    return cases, source_by_id


def document_sha256(document):
    return sha256(str(document.page_content).encode("utf-8", errors="replace")).hexdigest()


def evidence_excerpts(case, documents, max_per_marker=10, width=360):
    results = []
    for marker in case.get("evidence", []):
        needle = normalize(marker)
        matches = []
        for document in documents:
            text = " ".join(str(document.page_content).split())
            normalized_text = normalize(text)
            if needle not in normalized_text:
                continue
            position = normalized_text.find(needle)
            # Normalization changes offsets, so centre approximately and always retain a
            # bounded excerpt; the reviewer can use page metadata for source lookup.
            start = max(0, min(len(text), position) - width // 3)
            matches.append(
                {
                    "page": document.metadata.get("page"),
                    "excerpt": text[start : start + width],
                    "content_sha256": document_sha256(document),
                }
            )
            if len(matches) >= max_per_marker:
                break
        results.append({"marker": marker, "matches": matches})
    return results


def append_review(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", type=Path, default=DEFAULT_INPUTS)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--reviewer", required=True, help="Reviewer name or stable handle")
    parser.add_argument("--trusted-corpus-index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--trust-local-index", action="store_true")
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--all", action="store_true", help="Re-review currently approved cases")
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.reviewer.strip():
        raise SystemExit("--reviewer must not be empty")
    if not args.trust_local_index:
        raise SystemExit(
            "Refusing to deserialize the corpus pickle without --trust-local-index."
        )
    try:
        cases, source_by_id = load_cases(args.inputs)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    review_records, parse_errors = read_review_records(args.reviews)
    review_errors = [*parse_errors, *validate_review_records(review_records)]
    if review_errors:
        raise SystemExit("Review log is invalid:\n- " + "\n- ".join(review_errors))
    existing = latest_reviews(review_records)
    if args.ids:
        selected = set(args.ids)
        cases = [case for case in cases if case["id"] in selected]
        missing = selected - {case["id"] for case in cases}
        if missing:
            raise SystemExit("Unknown case IDs: " + ", ".join(sorted(missing)))

    with args.trusted_corpus_index.open("rb") as stream:
        docstore, _ = pickle.load(stream)  # noqa: S301 - explicit trust acknowledgement
    documents = list(docstore._dict.values())

    reviewed = 0
    for index, case in enumerate(cases, 1):
        digest = case_content_sha256(case)
        previous = existing.get(case["id"])
        if (
            not args.all
            and previous
            and previous.get("decision") == "approved"
            and previous.get("case_content_sha256") == digest
        ):
            continue
        print("\n" + "=" * 80)
        print(f"[{index}/{len(cases)}] {case['id']} | {case['category']}")
        print(f"Question: {case['question']}")
        print(f"Reference: {case['reference_answer']}")
        print(f"Answerable: {case['answerable']}")
        print(f"Risk tags: {case.get('risk_tags', [])}")
        print(f"Accepted: {case['acceptable_answers']}")
        if case.get("acceptable_answer_groups"):
            print(f"Required answer groups: {case['acceptable_answer_groups']}")
        if case["answerable"]:
            evidence_candidates = []
            for evidence in evidence_excerpts(case, documents):
                print(f"Evidence marker: {evidence['marker']!r}")
                for match in evidence["matches"]:
                    if match["content_sha256"] not in {
                        candidate["content_sha256"] for candidate in evidence_candidates
                    }:
                        evidence_candidates.append(match)
                    candidate_number = next(
                        number for number, candidate in enumerate(evidence_candidates, 1)
                        if candidate["content_sha256"] == match["content_sha256"]
                    )
                    print(
                        f"  [{candidate_number}] page {match['page']} "
                        f"sha={match['content_sha256'][:12]}: {match['excerpt']}"
                    )
        else:
            evidence_candidates = []
            print(
                "NEGATIVE CASE: approval asserts the answer/premise is absent or false "
                "in this exact corpus snapshot; automated search cannot prove this."
            )
        print(
            "Checklist: unambiguous question; correct/complete reference; valid accepted "
            "answers; specific evidence or verified absence; correct category and risk tags."
        )
        choice = input("[a]pprove / [r]eject / [s]kip / [q]uit: ").strip().lower()
        if choice == "q":
            break
        if choice == "s" or choice not in {"a", "r"}:
            continue
        notes = input("Review notes (required for rejection): ").strip()
        if choice == "r" and not notes:
            print("Rejection was not recorded because notes are required.")
            continue
        selected_hashes = []
        if choice == "a" and case["answerable"]:
            raw_selection = input(
                "Gold supporting chunk numbers (comma-separated, at least one): "
            ).strip()
            try:
                selections = [int(item.strip()) for item in raw_selection.split(",") if item.strip()]
            except ValueError:
                selections = []
            if not selections or any(
                number < 1 or number > len(evidence_candidates) for number in selections
            ):
                print("Approval was not recorded: select valid supporting chunk numbers.")
                continue
            selected_hashes = list(dict.fromkeys(
                evidence_candidates[number - 1]["content_sha256"] for number in selections
            ))
        source = source_by_id[case["id"]]
        record = {
            "case_id": case["id"],
            "case_content_sha256": digest,
            "decision": "approved" if choice == "a" else "rejected",
            "reviewer": args.reviewer.strip(),
            "reviewed_at": datetime.now().astimezone().isoformat(),
            "checklist_version": REVIEW_CHECKLIST_VERSION,
            "notes": notes,
            "source_dataset": source["path"],
            "source_dataset_sha256": source["dataset_sha256"],
            "corpus_index_sha256": sha256(
                args.trusted_corpus_index.read_bytes()
            ).hexdigest(),
            "gold_evidence_chunk_sha256": selected_hashes,
        }
        append_review(args.reviews, record)
        existing[case["id"]] = record
        reviewed += 1
        print(f"Recorded {record['decision']} for {case['id']}.")
    print(f"Session recorded {reviewed} decisions in {args.reviews}.")


if __name__ == "__main__":
    main()
