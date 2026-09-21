# Golden dataset review guide

The repository deliberately separates the 13-case seed dataset from the 39-case
candidate pool. Source lookup can confirm that positive evidence exists, but it
cannot prove that a fact is absent from the book or that a false-premise question
is well designed. A formal benchmark therefore requires a human reviewer.

## Approval checklist

Review every record in `dataset.jsonl` and `dataset_candidates.jsonl` against the
trusted local source. Approve a case only when all applicable checks pass:

1. The question has exactly the intended scope. A deliberately underspecified
   case must explicitly test clarification rather than have an arbitrary answer.
2. The reference answer is correct and complete.
3. Every accepted phrase is sufficient evidence of a correct answer. For
   multi-part answers, `acceptable_answer_groups` requires at least one phrase
   from every group.
4. Positive evidence markers are specific, relevant, and present in the source;
   they are not merely common words that happen to occur elsewhere.
5. For every positive case, select at least one displayed chunk that actually
   supports the reference answer. Do not select it merely because it contains a marker.
6. An unanswerable case really is absent from this corpus snapshot.
7. An adversarial case clearly defines its tested behavior: correct a false premise,
   resist an injection, protect a secret, or request clarification.
8. The category (`single_hop`, `reasoning`, `multi_hop`, `unanswerable`, or
   `adversarial`) matches the reasoning actually required.
9. Every `risk_tag` accurately describes the behavior being tested; ordinary
   positive cases do not need a risk tag.

Do not manually change `review_status` to manufacture approval. Use the review
command below after completing these checks. It appends a decision bound to the
case-content SHA256, corpus-index SHA256, reviewer, timestamp, and checklist
version. A later case or corpus edit makes the approval stale automatically.
Reject and fix or remove an invalid case rather than approving it to reach a
target count.

## Commands

Validate structure and locate positive evidence in the trusted local FAISS text:

```powershell
venv\Scripts\python.exe evaluation\audit_dataset.py `
  --dataset evaluation\dataset_candidates.jsonl `
  --trusted-corpus-index chunks_vector_store\index.pkl `
  --min-cases 39
```

Run the interactive review. The trust acknowledgement is mandatory because the
local FAISS docstore is a pickle. Positive cases show numbered source excerpts
and require exact supporting chunk selection before approval;
negative/adversarial cases require the reviewer to verify absence or false
premise against this exact corpus snapshot:

```powershell
venv\Scripts\python.exe evaluation\review_progress.py --format markdown

venv\Scripts\python.exe evaluation\export_review_packet.py `
  --trust-local-index

venv\Scripts\python.exe evaluation\review_dataset.py `
  --reviewer your-stable-handle `
  --trust-local-index
```

Do not try to review all 52 records in one sitting. Start with a three-case batch and
replace `your-stable-handle` with a consistent reviewer name that you will reuse:

```powershell
venv\Scripts\python.exe evaluation\review_dataset.py `
  --reviewer your-stable-handle `
  --trust-local-index `
  --ids hp1-012 hp1-013 hp1-043
```

These first three cases test knowledge absence. Read their bounded concordance in
`docs/interview/evidence/REVIEW_PACKET_2026-09-14.md`, then independently confirm the
fact is absent from this exact book snapshot. A zero search hit is insufficient. If
uncertain, reject or stop and investigate; never approve merely to advance progress.

The progress command is read-only. It distinguishes current approvals from
missing, rejected, case-stale, corpus-stale, and semantically invalid approvals.
Its next batch prioritizes adversarial/unanswerable cases because automated
source lookup cannot establish absence, followed by multi-hop and reasoning cases.

The export command writes the next risk-prioritized batch to
`evaluation/review_packets/next_batch.md`. Positive cases include bounded exact
chunk candidates and hashes. Negative/adversarial cases use explicitly reviewed
`review_search_terms` to provide bounded concordance only; hits help navigation,
and zero hits are not proof of absence. The packet is ignored by Git, contains no
automatic approval path, and must be followed by the interactive decision tool.

Decisions are appended to `evaluation/reviews.jsonl`; a later decision for the
same case supersedes an earlier one. Commit the review log as benchmark
provenance, after checking that notes contain no sensitive information.

After all 52 current records are approved, build a separate formal dataset. This command
verifies the current case hashes and corpus hash against the review log, refuses
missing/rejected/stale approvals, and will not overwrite an existing output
unless `--overwrite` is passed:

```powershell
venv\Scripts\python.exe evaluation\build_formal_dataset.py
```

Then execute the protected formal benchmark:

```powershell
venv\Scripts\python.exe evaluation\run_evaluation.py `
  --dataset evaluation\dataset_formal.jsonl `
  --formal --judge
```

`--formal` rejects fewer than 50 cases, partial system selections, `--limit`,
`--ids`, missing judge scoring, and any record not marked `human_approved`.
Formal retrieval evaluation uses embedded exact chunk hashes; non-formal data
continues to label marker-based relevance explicitly as a proxy.
