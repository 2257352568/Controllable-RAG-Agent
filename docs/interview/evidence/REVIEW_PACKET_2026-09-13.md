# Human-review packet evidence — 2026-09-13

## Purpose

Reduce the navigation cost of the first risk-prioritized human-review batch without turning retrieval output into an automatic approval.

## Reproduction

```powershell
.\venv\Scripts\python.exe evaluation\export_review_packet.py --trust-local-index
```

The generated worksheet is `evaluation/review_packets/next_batch.md`. It is Git-ignored because it contains bounded excerpts from the local corpus.

## Bound inputs

- Checklist version: `2026-09-12.2`
- Corpus index SHA256: `b2f74c7eace8a8517d27e027cfea18e50098febec4ed2af6f5af10a7f9aaa26b`
- `dataset.jsonl` SHA256: `2647a070778955decccc3d895f3dceb8293718defa44de90a26aabac182b7edb`
- `dataset_candidates.jsonl` SHA256: `0756158bba079262de77ae17f41aeba1e64e1c10d1e5fffe0c20805aecaff59c`

Historical experiment records retain the older dataset hashes that were current when those runs executed. They are not rewritten to match this metadata-only review change.

## Exported batch

The 10 cases are `hp1-012`, `hp1-013`, and `hp1-043` through `hp1-050`.

For negative cases, each configured `review_search_terms` marker returns at most two concordance hits, with each displayed excerpt capped at 240 characters and identified by chunk SHA256. A hit is navigation evidence only; zero hits are not proof that the information is absent from the corpus.

## Approval boundary

- The Markdown checkboxes cannot be imported as review decisions.
- Final approve/reject decisions must be recorded with `evaluation/review_dataset.py` after source review.
- Negative approvals cannot carry a positive supporting chunk.
- Current authoritative progress remains `0/50`; no human decision was created by this export.
