"""Report hash-aware human-review progress without modifying review decisions."""

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.review_dataset import (
    DEFAULT_INDEX,
    DEFAULT_INPUTS,
    DEFAULT_REVIEWS,
    load_cases,
)
from evaluation.review_workflow import (
    read_review_records,
    review_progress,
    validate_review_records,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", type=Path, default=DEFAULT_INPUTS)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--trusted-corpus-index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--next-limit", type=int, default=10)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    return parser.parse_args(argv)


def render_markdown(report):
    lines = [
        "# Human review progress",
        "",
        f"- Approved: {report['approved_cases']}/{report['total_cases']}",
        f"- Remaining: {report['remaining_cases']}",
        f"- Completion: {report['completion_rate']:.2%}",
        f"- Formal gate ready: {'yes' if report['ready_for_formal'] else 'no'}",
        "",
        "## Status counts",
        "",
    ]
    lines.extend(
        f"- {status}: {count}"
        for status, count in report["status_counts"].items()
    )
    lines.extend(["", "## Next review batch", ""])
    lines.extend(f"- {case_id}" for case_id in report["next_review_ids"])
    if not report["next_review_ids"]:
        lines.append("- none")
    if report["orphan_review_ids"]:
        lines.extend(["", "## Orphan review records", ""])
        lines.extend(f"- {case_id}" for case_id in report["orphan_review_ids"])
    return "\n".join(lines) + "\n"


def main(argv=None):
    args = parse_args(argv)
    if args.next_limit <= 0:
        raise SystemExit("--next-limit must be greater than zero")
    if not args.trusted_corpus_index.is_file():
        raise SystemExit(f"Missing corpus index: {args.trusted_corpus_index}")
    try:
        cases, _ = load_cases(args.inputs)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    records, parse_errors = read_review_records(args.reviews)
    errors = [*parse_errors, *validate_review_records(records)]
    if errors:
        raise SystemExit("Review log is invalid:\n- " + "\n- ".join(errors))
    report = review_progress(
        cases,
        records,
        sha256(args.trusted_corpus_index.read_bytes()).hexdigest(),
        args.next_limit,
    )
    if args.format == "markdown":
        print(render_markdown(report), end="")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
