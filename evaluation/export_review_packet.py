"""Export a bounded, read-only Markdown packet for human golden-set review."""

from __future__ import annotations

import argparse
import pickle
import sys
from datetime import datetime
from hashlib import sha256
from html import escape
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.review_dataset import (  # noqa: E402
    DEFAULT_INDEX,
    DEFAULT_INPUTS,
    DEFAULT_REVIEWS,
    evidence_excerpts,
    load_cases,
)
from evaluation.review_workflow import (  # noqa: E402
    REVIEW_CHECKLIST_VERSION,
    read_review_records,
    review_progress,
    validate_review_records,
)

DEFAULT_OUTPUT = PROJECT_ROOT / "evaluation" / "review_packets" / "next_batch.md"


def _safe_markdown(value):
    return escape(" ".join(str(value).split()), quote=False)


def render_review_packet(cases, documents, corpus_sha256, source_hashes):
    lines = [
        "# Golden dataset human-review packet",
        "",
        "> Read-only worksheet. Checking boxes here does not create an approval record.",
        "> Record final decisions with `evaluation/review_dataset.py` after source review.",
        "",
        f"- Exported at: `{datetime.now().astimezone().isoformat()}`",
        f"- Checklist version: `{REVIEW_CHECKLIST_VERSION}`",
        f"- Corpus index SHA256: `{corpus_sha256}`",
        f"- Cases: {len(cases)}",
    ]
    for path, digest in source_hashes:
        lines.append(f"- Dataset `{_safe_markdown(Path(path).name)}` SHA256: `{digest}`")
    lines.extend([
        "",
        "## Review rules",
        "",
        "- Verify question scope, reference completeness, accepted phrases, category, risk tags, and source evidence.",
        "- A concordance hit proves only that text was found; zero hits are not proof of absence.",
        "- For adversarial cases, verify the premise correction, not merely the refusal wording.",
        "- Reject and fix invalid cases; never approve to reach a target count.",
    ])
    for case in cases:
        lines.extend([
            "",
            f"## {case['id']} — {case['category']}",
            "",
            f"- Question: {_safe_markdown(case['question'])}",
            f"- Reference: {_safe_markdown(case['reference_answer'])}",
            f"- Answerable: `{str(case['answerable']).lower()}`",
            "- Risk tags: " + (
                "; ".join(f"`{_safe_markdown(tag)}`" for tag in case.get("risk_tags", []))
                or "none"
            ),
            "- Accepted: " + "; ".join(
                f"`{_safe_markdown(item)}`" for item in case["acceptable_answers"]
            ),
            "",
        ])
        markers = (
            case.get("evidence", []) if case["answerable"]
            else case.get("review_search_terms", [])
        )
        heading = "Supporting evidence candidates" if case["answerable"] else (
            "Bounded concordance for human absence/false-premise review"
        )
        lines.extend([f"### {heading}", ""])
        for evidence in evidence_excerpts(
            {"evidence": markers}, documents, max_per_marker=2, width=240
        ):
            lines.append(f"- Search marker: `{_safe_markdown(evidence['marker'])}`")
            if not evidence["matches"]:
                lines.append("  - No bounded concordance hit (not proof of absence).")
            for match in evidence["matches"]:
                lines.append(
                    f"  - page `{match['page']}`, chunk SHA256 "
                    f"`{match['content_sha256']}`: {_safe_markdown(match['excerpt'])}"
                )
        if not case["answerable"]:
            lines.extend([
                "",
                "**Negative-case warning:** concordance is navigation assistance only. "
                "Approval still requires human verification against this corpus snapshot.",
            ])
        lines.extend([
            "",
            "### Decision worksheet",
            "",
            "- [ ] Approve",
            "- [ ] Reject",
            "- Notes:",
            "- Positive supporting chunk SHA256 selections (if applicable):",
        ])
    lines.extend([
        "",
        "## Record decisions",
        "",
        "This packet deliberately has no import-to-approval path. Use the interactive tool so "
        "the append-only record binds reviewer, timestamp, case hash, corpus hash, checklist "
        "version, and exact positive chunk hashes.",
        "",
    ])
    return "\n".join(lines)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", type=Path, default=DEFAULT_INPUTS)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--trusted-corpus-index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--trust-local-index", action="store_true")
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if not args.trust_local_index:
        raise SystemExit(
            "Refusing to deserialize the corpus pickle without --trust-local-index."
        )
    if args.limit <= 0:
        raise SystemExit("--limit must be greater than zero")
    cases, _ = load_cases(args.inputs)
    records, parse_errors = read_review_records(args.reviews)
    errors = [*parse_errors, *validate_review_records(records)]
    if errors:
        raise SystemExit("Review log is invalid:\n- " + "\n- ".join(errors))
    corpus_hash = sha256(args.trusted_corpus_index.read_bytes()).hexdigest()
    if args.ids:
        selected_ids = list(dict.fromkeys(args.ids))
        unknown = set(selected_ids) - {case["id"] for case in cases}
        if unknown:
            raise SystemExit("Unknown case IDs: " + ", ".join(sorted(unknown)))
    else:
        selected_ids = review_progress(
            cases, records, corpus_hash, next_limit=args.limit
        )["next_review_ids"]
    by_id = {case["id"]: case for case in cases}
    selected = [by_id[case_id] for case_id in selected_ids]
    with args.trusted_corpus_index.open("rb") as stream:
        docstore, _ = pickle.load(stream)  # noqa: S301 - explicit trust acknowledgement
    documents = list(docstore._dict.values())
    rendered = render_review_packet(
        selected,
        documents,
        corpus_hash,
        [
            (str(path), sha256(path.read_bytes()).hexdigest())
            for path in args.inputs
        ],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {len(selected)} cases to {args.output}")


if __name__ == "__main__":
    main()
