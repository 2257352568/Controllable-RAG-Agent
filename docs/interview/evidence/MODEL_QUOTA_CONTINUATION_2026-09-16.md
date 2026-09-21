# Model-quota continuation (exploratory)

The 52-case formal dataset remains unchanged (SHA256
`5a713470ef679196c07d92bb709ec6a49319eeceeff4f096b2bc389142ea3bf3`).
The `qwen3.7-flash` run completed all 468 case/system/repetition slots, but its
free quota was exhausted after `hp1-039`. Direct and naive RAG each have 117
successful records for `hp1-001`–`hp1-039`; Agentic RAG has 103 successful
records in that span, with additional non-quota failures. The complete run is
retained under `evaluation/results/formal-run-20260916-v2/` and failed the
pre-registered quality gate. Its failed quota records must not be interpreted
as model-quality observations.

To avoid reusing 39 cases' model calls, `hp1-040`–`hp1-052` are evaluated
separately with `qwen3.7-flash-2026-07-15`, while the judge remains
`deepseek-v4-pro-0813`. Both RAG systems use the same `chunks` source. This
run is **not formal mode** and cannot be spliced into a single fixed-model
formal score or marked as passing `formal-quality-2026-09-16.1`.

The snapshot-model preflight showed successful Direct and naive-RAG calls on
`hp1-040`, but Agentic RAG reached the graph recursion limit. The continuation
therefore preserves Agent failures rather than silently replacing them with a
different architecture or increasing the limit post hoc. Report results by
generation-model stratum and by case/system/repetition, with failed slots and
cost/latency shown explicitly. A fixed-model 52-case release claim remains
unproven.
