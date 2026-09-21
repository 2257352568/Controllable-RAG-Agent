# Controllable Agentic RAG

一个用于系统学习 Agentic RAG 的面试型项目：以 LangGraph 编排多源检索、证据判断、
引用生成、拒答和预算终止，并用同一数据集比较 direct、naive RAG 与 Agentic RAG。
项目强调流程清楚、结果可复现和失败可解释，不宣称生产级能力或 Agent 优于普通 RAG。

## 来源与个人工作

本项目基于 NirDiamant 的
[Controllable-RAG-Agent](https://github.com/NirDiamant/Controllable-RAG-Agent)
继续学习和改造，并保留原 Apache-2.0 License。上游提供原始 LangGraph 工作流、
Harry Potter 示例语料及主要节点思路；本仓库的个人工作集中在百炼兼容模型迁移、
配置与模块拆分、引用/拒答与预算控制、FastAPI/SSE、Trace、离线测试、人工审核数据集、
三路径评测和失败复盘。详细边界见
[`docs/interview/PROJECT_STORY.md`](docs/interview/PROJECT_STORY.md)。

当前 52/52 条评测样本已完成人工审核，213 项离线测试通过；正式质量门禁仍未通过，
因此只能把它描述为“可运行、可评测的学习型项目”，不能写效果提升。零基础阅读入口见
[`docs/interview/START_HERE.md`](docs/interview/START_HERE.md)，完整就绪审计见
[`docs/interview/evidence/RESUME_READINESS_AUDIT_2026-09-21.md`](docs/interview/evidence/RESUME_READINESS_AUDIT_2026-09-21.md)。

## Evaluation

Citation-attribution regression probe (paid Qwen calls):

```powershell
venv\Scripts\python.exe evaluation\run_citation_grounding_probe.py
```

This separate diagnostic uses four synthetic cases and compares full evidence
against selected-source evidence in the distillation and answer verifiers, with
the same current prompt/model in both variants (16 logical calls). It records
dataset/code hashes, configuration, each decision/error, tokens and latency.
The fixture is `citation_grounding_cases.json`, not human-reviewed gold data;
the probe does not measure retrieval or complete Agent answer quality. Results
and interpretation: `docs/interview/evidence/CITATION_GROUNDING_PROBE_2026-09-14.md`.

Structured sentence-to-evidence compatibility probe (paid Qwen calls):

```powershell
venv\Scripts\python.exe evaluation\run_claim_citation_probe.py
```

This exercises two synthetic single/multi-fact cases through the compiled answer
generation and grounding subgraph. It verifies complete sentence mappings,
expected source coverage, errors, retries, tokens and latency; it does not run
retrieval or the full Agent. See
`docs/interview/evidence/CLAIM_CITATION_PROBE_2026-09-14.md`.

This benchmark compares three systems on the same questions:

- `direct`: Qwen without retrieval.
- `naive-rag`: one retrieval pass over all three FAISS stores followed by one answer call.
- `agentic-rag`: the complete LangGraph planning and replanning workflow.

The 13-case seed dataset contains single-hop, reasoning, multi-hop, and
unanswerable questions. A separate 39-case candidate pool adds adversarial,
belief/fact-conflict, and underspecified cases and brings the review queue to 52.
Candidates are not formal gold data until a
human records hash-bound approvals under `REVIEW_GUIDE.md`; the formal builder,
not a manual status edit, materializes `review_status=human_approved` together
with verifiable provenance.

Audit the pre-registered category and risk matrix without model calls:

```powershell
venv\Scripts\python.exe evaluation\audit_risk_coverage.py
```

`risk-coverage-2026-09-14.1` is a lightweight learning and CI matrix. Passing it
proves only that required risk types are represented, not that labels are correct
or the system handles them.

Run a cheap smoke test first:

```powershell
venv\Scripts\python.exe evaluation\run_evaluation.py --systems direct naive-rag --limit 2
```

Run the full deterministic benchmark:

```powershell
venv\Scripts\python.exe evaluation\run_evaluation.py
```

Evaluate dense chunk retrieval without a chat-model call:

```powershell
venv\Scripts\python.exe evaluation\run_retrieval_evaluation.py `
  --dataset evaluation\dataset.jsonl `
  --ks 1 3 5 10 `
  --trust-local-index
```

Compare dense, BM25, and equal-weight RRF hybrid retrieval on those same cases
(one embedding query per case and no chat-model calls):

```powershell
venv\Scripts\python.exe evaluation\run_hybrid_retrieval_evaluation.py `
  --trust-local-index --ks 1 3 5 10 `
  --candidate-pool 50 --rrf-constant 60
```

The report records dataset/index hashes, model, candidate pool, RRF/BM25
parameters, top-document hashes, and per-system latency. Without completed human
review, this remains a marker-proxy screen rather than formal Recall. Do not tune
weights repeatedly on the same 11 cases and then claim generalization.

Run the generator context-reliance diagnostic with frozen nonce facts. Each case
is evaluated without context, with its original synthetic fact, and with a paired
counterfactual that changes only the target answer:

```powershell
venv\Scripts\python.exe evaluation\run_context_reliance_evaluation.py
```

This detects obvious prior-answer leakage and context-insensitive generation. It
does not invoke a retriever and must not be reported as end-to-end RAG quality.

Run the same paired facts through real Qwen embeddings, two isolated in-memory
FAISS indexes, Top-1 retrieval, and Qwen generation:

```powershell
venv\Scripts\python.exe evaluation\run_private_rag_reliance_evaluation.py
```

The two indexes prevent original and counterfactual facts from appearing in one
candidate set. This is an end-to-end naive-RAG diagnostic, not the full LangGraph
agent or a substitute for the 50+ human-reviewed benchmark.

Screen chunk-size candidates without any model API call. This reconstructs a
derived page corpus from the current chunk index and evaluates BM25 only; it is
for narrowing the later paid dense experiment, not for claiming a Qwen optimum:

```powershell
venv\Scripts\python.exe evaluation\run_chunking_ablation.py `
  --trust-local-index `
  --output evaluation\results\chunking-bm25.json
```

The command reports Hit@K, Precision@K, Recall@K, MRR@K, nDCG@K, and
evidence-marker recall, with overall and category slices. Human review now
requires exact supporting chunk selection for every answerable approval, and
formal retrieval uses those content SHA256 labels. Until that review is complete,
document relevance is only a lexical evidence-marker proxy. Do not report proxy
values as an exhaustive retrieval benchmark. The trust flag is mandatory because
the FAISS docstore is a pickle.

Recover the upstream quote index's missing page metadata without re-embedding:

```powershell
venv\Scripts\python.exe evaluation\repair_quote_locations.py `
  --trust-local-index --write
venv\Scripts\python.exe evaluation\audit_ingestion.py --trust-local-index
```

The repair reconstructs pages from the chunk index and accepts normalized exact
matches only. A unique match receives `page`; an ambiguous match receives only
`location_candidates`; any missing match makes the command fail. Writing is
atomic, leaves `index.faiss` unchanged, and refreshes `index_manifest.json`.

Audit schema and evidence markers without calling a model:

```powershell
venv\Scripts\python.exe evaluation\audit_dataset.py `
  --trusted-corpus-index chunks_vector_store\index.pkl `
  --min-cases 13
```

Enable Qwen-as-a-judge for correctness, relevance, and faithfulness scores:

```powershell
venv\Scripts\python.exe evaluation\run_evaluation.py --judge
```

Complete hash-bound human review, then build `dataset_formal.jsonl` and use the
protected formal mode. The append-only review log binds each decision to case
content, corpus snapshot, reviewer, timestamp, and checklist version. The build
rejects missing, rejected, stale, or undersized approvals; the benchmark rejects
partial runs:

```powershell
venv\Scripts\python.exe evaluation\review_progress.py --format markdown

venv\Scripts\python.exe evaluation\export_review_packet.py --trust-local-index
venv\Scripts\python.exe evaluation\review_dataset.py `
  --reviewer your-stable-handle --trust-local-index
venv\Scripts\python.exe evaluation\build_formal_dataset.py
venv\Scripts\python.exe evaluation\run_evaluation.py `
  --dataset evaluation\dataset_formal.jsonl --formal --judge --repetitions 3
```

The progress report never creates approvals. It reports stale/rejected/missing
records separately and prints a risk-prioritized next batch.

Formal mode applies pre-registered protocol `formal-quality-2026-09-16.1` after
persisting details, summary and failures. It requires absolute Agent quality,
structural citation, safety and repeat-stability thresholds, plus a statistically
favored Agent result over naive RAG on at least one primary metric with effect
size at least 0.03 and no significant primary regression. A failed gate preserves
the evidence files but returns a non-zero exit code. Recheck a saved result with:

```powershell
venv\Scripts\python.exe evaluation\verify_formal_quality.py `
  --summary evaluation\results\summary-<timestamp>.json `
  --details evaluation\results\details-<timestamp>.jsonl `
  --dataset evaluation\dataset_formal.jsonl
```

The thresholds were fixed before the formal result exists. They are project
release targets, not industry standards, and must not be relaxed after seeing a
failed run; fix or simplify the system and run a new versioned experiment instead.
The saved-result verifier recomputes every system aggregate and paired bootstrap
from JSONL details, compares the result with the saved summary, and then applies
the protocol. It also checks the dataset hash, immutable case fields, and the
complete case × system × repetition product. A details checksum alone would not
detect summary-only edits or prove that the intended cases were evaluated.

After the benchmark, audit at least 20% of judge-scored outputs. Sampling is
stratified by system and category, then ranked deterministically from a fixed
seed. Reviews bind both the whole details-file SHA256 and the individual record
SHA256, so changed answers or judge outputs invalidate old reviews:

```powershell
venv\Scripts\python.exe evaluation\review_judge.py `
  --details evaluation\results\details-<timestamp>.jsonl `
  --reviewer your-stable-handle

venv\Scripts\python.exe evaluation\review_judge.py `
  --details evaluation\results\details-<timestamp>.jsonl `
  --report-only --require-complete --require-quality-gate
```

The report contains coverage, mean absolute error, and agreement within the
configured score tolerance for correctness, relevance, and applicable
faithfulness judgments. Bounded excerpts from the same retrieved context shown to
the judge are retained in ignored result files for faithfulness review; treat those files as potentially sensitive
corpus data and do not commit them. Protocol `judge-audit-2026-09-12.1`
predeclares 20% sampling, 0.2 score tolerance, at least 80% agreement within that
tolerance, MAE no greater than 0.2, and 100% completion of the selected records.
These are project release thresholds, not claimed industry standards; do not
change them after inspecting the formal result.

See `REVIEW_GUIDE.md` before approving any case. An automated evidence lookup is
not a human approval, especially for negative and adversarial examples.

Use `--ids hp1-009 hp1-010` to select cases. Budget ablations support
`--max-steps 4`, `--max-model-requests 10`, and `--max-total-tokens 5000`.
The shared chat-model factory enforces the latter two before logical invocation:
it atomically claims a request slot and conservatively reserves input/schema,
maximum output, and protocol headroom, then settles against provider usage.
The outer callback remains an independent node-level audit/fallback. Embeddings
and individual HTTP retries inside the provider SDK are excluded. Results are written to
`evaluation/results/` as detailed JSONL and aggregate JSON. Do not put benchmark
numbers on a resume until the full run has completed successfully and its result
files have been preserved.

Source/threshold controls are part of the recorded experiment configuration:

```powershell
venv\Scripts\python.exe evaluation\run_evaluation.py `
  --systems naive-rag agentic-rag `
  --enabled-sources chunks quotes `
  --min-evidence-records 2 `
  --limit 2
```

Disabled sources are skipped and never loaded by the naive baseline. The Agent
passes the allowlist to planning/routing/replanning and enforces it again at the
graph route and retrieval node. A blocked attempt is recorded and fed back to
replanning. The minimum applies to unique IDs in grounded, allowlisted Agent
evidence and is checked before answerability and final generation. It does not
claim that two records represent two independent facts.

Use `--repetitions 3` to run each case/system independently several times. The
summary then reports unique cases separately from runs, plus all-runs execution
success, all-runs answer hit, termination consistency, and answerability
consistency. With one repetition these stability fields are `null`, because one
observation cannot establish repeatability.

Use `--persist-traces` to write a privacy-minimized per-Agent-run file under
`RAG_TRACE_DIR` (default `runtime_traces`). Verify one file with:

```powershell
venv\Scripts\python.exe evaluation\verify_trace.py runtime_traces\<trace-id>.json
```

The trace excludes questions, prompts, retrieved context and answers. Its SHA256
detects corruption or edits where the checksum was not recomputed; it is not a
signature or proof against an attacker who can rewrite both fields.

Every run also writes `failures-<timestamp>.json`. A record can carry multiple
diagnostic labels: execution error, answer miss, answerability error, evidence
miss, step/request/token-budget exhaustion, grounding failure, or a judge score
below 0.5.

Evaluation retries are limited to transient network failures and HTTP
408/409/425/429/5xx responses. Deterministic contract failures and HTTP
400/401/403/404/405/422 fail immediately. Details and summaries retain attempts,
retryability, error class, retry rate, and recovery rate. This outer retry is
separate from provider-SDK internal retries, which are not yet individually observed.

## Metrics

- `answer_hit`: whether an accepted answer phrase occurs in the response.
- `acceptable_answer_groups`: optional AND-of-OR groups for multi-part answers;
  every group must match so a partial answer cannot receive a full hit.
- `token_f1`: deterministic token overlap with the reference answer.
- `answerability_decision_accuracy`: whether the system answered answerable cases and abstained on unanswerable cases.
- `abstention_precision` / `abstention_recall`: refusal quality; the current refusal detector is lexical and must be human-audited.
- `secret_leak_rate`: whether a response contains a configured runtime secret. Only
  a boolean is recorded; secret values never enter result files.
- `evidence_recall`: fraction of gold evidence markers found in retrieved context;
  zero documents/citations with a non-empty gold list scores `0`, while `null`
  means no gold denominator exists.
- retrieval-only marker-proxy Hit/Precision/Recall/MRR/nDCG@K and evidence-marker
  recall@K: useful for Top-K regression, but not a substitute for exact human
  relevant-chunk labels.
- `citation_evidence_recall`: fraction of gold evidence markers covered by the
  documents actually cited by the answer.
- `citation_precision`: fraction of cited documents containing at least one gold
  evidence marker. This lexical metric is a regression signal, not claim-level entailment.
- `citation_count`: number of model-selected citations that resolve to real
  retrieved evidence. Invented IDs are discarded before rendering.
- `claim_citation_coverage`: fraction of normalized answer sentences represented
  by the Agent's claim map. It is structural, not semantic entailment.
- `claim_citation_id_validity`: fraction of mapped IDs present in the final cited
  document set.
- `claim_citation_contract_pass`: requires complete, ordered, non-duplicate
  sentence mappings and at least one valid evidence ID per claim.
- `claim_citation_validation_failed`: records a final schema/validation failure,
  including runs that correctly terminate without an answer.
- `error_rate`, mean/P50/P95 latency, steps, request count, and token usage: operational behavior.
- termination reason, budget exhaustion rate, and per-node mean/P95 latency: Agent control and diagnosis.
- `node_usage` and structured error diagnostics: per-node chat request/Token
  totals and means, plus failed node, duration, and exception type without raw
  provider error text.
- repeat stability: strict per-case all-runs success/hit plus termination and
  answerability consistency; reported only for cases with at least two runs.
- pairwise 95% bootstrap confidence intervals: compare systems on identical case
  IDs after averaging complete repetitions. A case is excluded for that metric if
  either system has an error, missing value, or unequal repetition count; fewer than 20 pairs can never
  produce a directional inference. Configure reproducibly with
  `--bootstrap-samples` and `--bootstrap-seed`; formal runs require at least 2,000
  resamples.
- `by_category`: quality, latency, error, and Token slices for each question type.
- `judge_correctness`, `judge_relevance`, and `judge_faithfulness`: optional model-judge scores.

The deterministic metrics are intentionally simple and suitable for regression
checks. Judge scores are more semantic but should be manually spot-checked and
reported together with the judge model name.
