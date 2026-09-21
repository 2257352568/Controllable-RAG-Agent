# Formal quality protocol 2026-09-16.1

## Purpose

This protocol replaces only the model allocation of
`formal-quality-2026-09-14.1`; all quality, safety, stability, repetition, and
bootstrap thresholds remain unchanged. The previous complete attempt was
invalidated by `qwen3.8-max` free-quota exhaustion, not by a quality result.
The replacement was registered before inspecting any full result from the new
models.

## Frozen configuration

- Generation model for Direct, naive RAG, and Agentic RAG:
  `qwen3.7-flash`.
- Independent judge model: `deepseek-v4-pro-0813`.
- Embedding model: `text-embedding-v4`, 1536 dimensions.
- Retrieval sources for both RAG systems: `chunks` only.
- Dataset: 52 human-approved cases, SHA256
  `5a713470ef679196c07d92bb709ec6a49319eeceeff4f096b2bc389142ea3bf3`.
- Three independent repetitions per case/system and 2,000 paired bootstrap
  samples with seed `20260912`.

Using a separate judge avoids evaluating a model with itself and keeps judge
usage outside the generation model's independent free quota. Restricting both
RAG systems to the same chunks index preserves an architecture-controlled
comparison and reduces token use; it is not a claim that chunks-only retrieval
is globally optimal.

## Unchanged release thresholds

- Each system: at least 50 unique cases, error rate no more than 5%, and zero
  detected secret leakage.
- Agentic RAG: answer hit at least 0.80, answerability accuracy at least 0.90,
  citation evidence recall at least 0.80, citation precision at least 0.75,
  judge correctness at least 0.80, relevance and faithfulness at least 0.85,
  claim-citation contract pass rate 1.0, validation failure no more than 0.02,
  and grounding failure no more than 0.10.
- Stability: all-run execution success at least 0.95 and termination and
  answerability consistency at least 0.90.
- Against naive RAG: at least one of answer hit, judge correctness, or judge
  faithfulness must improve by at least 0.03 with a paired 95% CI favoring the
  Agent; no primary metric may significantly regress.

The machine-readable source of truth is `evaluation/formal_quality.py`.
