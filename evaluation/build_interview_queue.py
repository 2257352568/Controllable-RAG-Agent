"""Generate or verify the prioritized interview study queue."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.interview_questions import parse_question_bank, render_study_queue

DEFAULT_SOURCE = PROJECT_ROOT / "docs" / "interview" / "QUESTION_BANK.md"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "interview" / "STUDY_QUEUE.md"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.limit <= 0:
        raise SystemExit("--limit must be greater than zero")
    questions = parse_question_bank(args.source.read_text(encoding="utf-8"))
    rendered = render_study_queue(args.source, questions, args.limit)
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(
                "Interview queue is stale; run: python evaluation/build_interview_queue.py"
            )
        print(f"Interview queue is current: {len(questions)} questions")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output} from {len(questions)} questions")


if __name__ == "__main__":
    main()
