"""Interactively audit a reproducible stratified sample of model-judge scores."""

import argparse
import json
import sys
from datetime import datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.judge_review import (
    AUDIT_PROTOCOL,
    JUDGE_REVIEW_VERSION,
    build_audit_report,
    record_key,
    record_sha256,
    select_audit_records,
)


def read_jsonl(path):
    records = []
    if not path.exists():
        return records
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                records.append((line_number, json.loads(line)))
    return records


def append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()


def score(prompt, allow_blank=False):
    while True:
        raw = input(prompt).strip()
        if allow_blank and not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            value = -1
        if 0 <= value <= 1:
            return value
        print("Enter a score from 0 to 1" + (" or blank" if allow_blank else "") + ".")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--details", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, default=PROJECT_ROOT / "evaluation" / "judge_reviews.jsonl")
    parser.add_argument("--reviewer", help="Stable reviewer handle; required unless --report-only")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--require-quality-gate", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.report_only and (not args.reviewer or not args.reviewer.strip()):
        raise SystemExit("--reviewer is required for interactive review")
    if not args.details.is_file():
        raise SystemExit(f"Details file not found: {args.details}")
    details_sha = sha256(args.details.read_bytes()).hexdigest()
    records = [record for _, record in read_jsonl(args.details)]
    selected = select_audit_records(
        records, AUDIT_PROTOCOL["sampling_rate"], AUDIT_PROTOCOL["sampling_seed"]
    )
    reviews = read_jsonl(args.reviews)
    latest = {review.get("record_key"): review for _, review in reviews}

    if not args.report_only:
        for index, record in enumerate(selected, 1):
            key = record_key(record)
            previous = latest.get(key)
            if previous and previous.get("details_sha256") == details_sha and previous.get("record_sha256") == record_sha256(record):
                continue
            print("\n" + "=" * 80)
            print(f"[{index}/{len(selected)}] {key} | {record.get('category')}")
            print(f"Question: {record.get('question')}")
            print(f"Reference: {record.get('reference_answer')}")
            print(f"Answer: {record.get('answer')}")
            for evidence in record.get("judge_context_audit_evidence", []):
                print(f"Evidence {evidence.get('id')}: {evidence.get('excerpt')}")
            print(f"Judge: {json.dumps(record.get('judge'), ensure_ascii=False)}")
            choice = input("[r]eview / [s]kip / [q]uit: ").strip().lower()
            if choice == "q":
                break
            if choice != "r":
                continue
            human_scores = {
                "correctness": score("Human correctness [0..1]: "),
                "relevance": score("Human relevance [0..1]: "),
            }
            faithfulness = score("Human faithfulness [0..1, blank if N/A]: ", allow_blank=True)
            if faithfulness is not None:
                human_scores["faithfulness"] = faithfulness
            review = {
                "record_key": key,
                "record_sha256": record_sha256(record),
                "details_sha256": details_sha,
                "reviewer": args.reviewer.strip(),
                "reviewed_at": datetime.now().astimezone().isoformat(),
                "review_version": JUDGE_REVIEW_VERSION,
                "human_scores": human_scores,
                "notes": input("Notes (optional): ").strip(),
            }
            append_jsonl(args.reviews, review)
            latest[key] = review
        reviews = read_jsonl(args.reviews)

    report = build_audit_report(
        records, selected, reviews, details_sha, AUDIT_PROTOCOL["score_tolerance"]
    )
    report["details"] = str(args.details.resolve())
    report["details_sha256"] = details_sha
    report["sampling"] = {
        "method": "SHA256-ranked stratified sample",
        "rate": AUDIT_PROTOCOL["sampling_rate"],
        "seed": AUDIT_PROTOCOL["sampling_seed"],
    }
    output = args.output or args.details.with_name(f"judge-audit-{args.details.stem}.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Report: {output}")
    if args.require_complete and not report["complete"]:
        raise SystemExit(1)
    if args.require_quality_gate and not report["quality_gate_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
