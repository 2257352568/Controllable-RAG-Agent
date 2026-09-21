# Retrieval-source and evidence-threshold smoke evidence

Date: 2026-09-12 (Asia/Shanghai)

## Claim under test

The configured retrieval-source allowlist is enforced outside the LLM prompt,
and the Agent cannot finalize below its configured minimum number of validated
evidence records.

## Deterministic verification

The offline suite contains explicit tests for:

- parsing, rejecting empty/unknown/duplicate source lists, and validating a
  positive evidence minimum;
- routing an LLM-selected disabled source to `retrieval_source_disabled` without
  invoking its retriever;
- overriding an LLM `can_be_answered=true` decision when the evidence minimum is
  not met;
- rejecting finalization below the minimum without calling the answer model;
- applying the same source selection to the naive-RAG evaluation baseline;
- recording both controls in the evaluation state.

The compiled-graph regression uses a real temporary FAISS index under a Unicode
directory. It first makes the mocked router choose disabled `quotes`, verifies
that no quotes/summaries index exists or loads, passes the policy feedback to
replanning, then retrieves allowed `chunks` and returns a validated citation.
The same suite proves duplicate evidence IDs count once, malformed Python/CLI
policy values fail before retrieval, and a direct subgraph call cannot bypass the
allowlist. The current repository-wide result is `Ran 106 tests ... OK`.

## Live Qwen integration smoke

Command:

```powershell
venv\Scripts\python.exe evaluation\run_evaluation.py `
  --systems naive-rag `
  --ids hp1-001 `
  --enabled-sources chunks `
  --min-evidence-records 1 `
  --retries 0
```

Recorded configuration and result:

- dataset SHA256: `cacf6e16c83089df1f9780aa35045e01d081794a1ec6929a97d4ee383380e25a`
- chat model: `qwen3.8-max`
- embedding model: `text-embedding-v4`, 1536 dimensions
- prompt version: `2026-09-12.1`
- enabled sources: `chunks` only
- retrieved documents: 1 (confirmed in the per-case JSONL)
- answer hit: 1.0; evidence recall: 1.0; cited-document precision: 1.0
- latency: 6.719 seconds; chat usage: 1 request / 343 tokens
- termination: `answered`; execution errors: 0

## Interpretation boundary

This one-case run proves that source selection propagates through a real
embedding/retrieval/generation evaluation path and is preserved in result
metadata. The Agent-side fail-closed route and evidence threshold are proven by
deterministic contract tests, not by this naive-RAG run. One case cannot establish
quality, stability, or a good threshold value, so none of the numbers above are
resume metrics. A formal ablation must compare fixed cases across source sets and
threshold values with repeated runs.

## Live Agent threshold smoke

The same `hp1-001` question was run through `agentic-rag` with only `chunks`,
`max_steps=1`, prompt/policy version `2026-09-12.2`, dataset hash above, and two
different minimums:

| Minimum | Retrieved validated IDs | Result | Requests / tokens | Latency |
|---:|---:|---|---:|---:|
| 2 | 1 | `step_budget_exhausted`; gate reason `1 below 2` | 7 / 3,933 | 16.385 s |
| 1 | 1 | Gate passed; final verifier returned `grounding_failed` | 12 / 6,751 | 31.297 s |

For minimum 2, `assess_answerability` used zero model requests because the
deterministic gate failed first. With minimum 1, the gate admitted the answer
path, but the stochastic verifier rejected a factually correct candidate with a
valid evidence ID. This separates control correctness from answer quality and
adds another reproducible example of verifier instability. Both are single-run
smokes, not threshold-quality or stability estimates.

The second run also exposed a metric bug: zero citations with expected gold
evidence produced `citation_evidence_recall=null`, which would disappear from a
mean. The evaluator now records zero in this case and reserves `null` for cases
without a gold-evidence denominator.

This repair was verified against Qwen with a one-request budget on the same case:
the run stopped after anonymization with `model_request_budget_exhausted`, no
documents and no citations; both `evidence_recall` and
`citation_evidence_recall` were `0.0`, while citation precision remained `null`
because there were no predicted citations. Recorded usage was 1 request / 395
tokens and 2.836 seconds. This is metric-semantics evidence, not model quality.
