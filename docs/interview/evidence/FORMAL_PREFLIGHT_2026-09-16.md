# Formal benchmark preflight

## Frozen inputs

- Human review: 52/52 approved; no rejected, stale, or invalid records.
- Formal dataset: `evaluation/dataset_formal.jsonl`.
- Dataset SHA256: `5a713470ef679196c07d92bb709ec6a49319eeceeff4f096b2bc389142ea3bf3`.
- Chat/judge model: `qwen3.8-max` through Alibaba Cloud Model Studio's OpenAI-compatible endpoint.
- Embedding model: `text-embedding-v4`, 1536 dimensions.
- Protocol: `formal-quality-2026-09-14.1`.

## Failure found by the first formal run

The first protected run was stopped on `hp1-001`. Direct generation worked, but
both retrieval systems failed because FAISS treated the circuit-breaker wrapper
as a deprecated callable embedding function and raised:

```text
TypeError: 'CircuitBreakerModel' object is not callable
```

The wrapper exposed `embed_query` and `embed_documents`, but FAISS selects its
modern path using `isinstance(embedding_function, Embeddings)`. Duck typing did
not preserve this nominal interface through the resilience adapter. Existing
unit tests checked methods and wrapper order but not the vector store's runtime
type branch.

## Fix and verification

- Added `CircuitBreakerEmbeddings`, which explicitly implements LangChain's
  `Embeddings` interface while retaining budget and circuit-breaker behavior.
- Added a regression assertion for the nominal interface.
- Replaced the deprecated Pydantic `.dict()` judge conversion with
  `.model_dump()`.
- Targeted tests: 43 passed.
- Full offline suite before the run: 207 passed.
- Ruff: passed.
- Online preflight: one human-approved case completed through naive RAG and
  Agentic RAG with Qwen judge; both had zero errors, answer hit 1.0, evidence
  recall 1.0, citation precision 1.0, and judge correctness/relevance/
  faithfulness 1.0. This is a plumbing check, not a quality estimate.

## Operational lesson

The foreground formal run later disappeared when its owning Codex execution
session ended, before the evaluator wrote its end-of-run result files. No
partial observations are being treated as benchmark evidence. The rerun is
launched as an independent background process with stdout/stderr logs. The
evaluator still lacks durable per-record checkpoint/resume, which remains a
known reliability gap rather than a claimed capability.

## First complete formal attempt

The independent run produced all 468 expected records (52 cases × 3 systems ×
3 repetitions). Independent verification confirmed the dataset hash, case
fields, unique case/system/repetition product, recomputed summary, and details
SHA256 (`8c69498c62d1dcfe1cf23d7437770e6711a861aa3bf83803bf41dace88e8429e`).
The quality gate correctly failed.

This is not interpretable as a model-quality result. All Direct and naive-RAG
runs through `hp1-005` completed, then the provider returned HTTP 403 from
`hp1-006` onward:

```text
AllocationQuota.FreeTierOnly: Free quota exhausted. To continue accessing the
model on a paid basis, add funds or disable the "use free tier only" mode.
```

Observed error rates were 90.38% for Direct, 90.38% for naive RAG, and 92.31%
for Agentic RAG. The shared onset and provider code identify an account quota
failure rather than evidence that all three architectures degraded together.
These metrics must not appear as resume quality claims. A clean full rerun is
required after the account permits paid usage. The invalid attempt is retained
as failure and release-gate evidence; judge calibration must wait for the clean
run.
