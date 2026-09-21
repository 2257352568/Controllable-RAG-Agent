# Project Working Agreement

## Primary objective

This repository exists to prepare its owner for AI Agent / RAG engineering
interviews. A feature is not complete merely because it runs. It should also
produce evidence the owner can explain and defend in an interview.

## Rules for future work

1. Preserve the upstream license and attribution. Never present upstream work as
   original work. Clearly distinguish upstream architecture from local changes.
2. Prefer measurable improvements over adding technology names. Never write an
   unverified metric in the README or resume material.
3. For every material change, update the relevant entry in
   `docs/interview/QUESTION_BANK.md` or `docs/interview/ROADMAP.md`.
4. Record important failures, root causes, trade-offs, and verification evidence;
   these are high-value interview material.
5. Keep evaluation results reproducible: record dataset hash, model, configuration,
   baseline, latency, token usage, and errors.
6. Prioritize work in this order: truthful ownership, correctness/evaluation,
   reliability, controllability, observability, performance, then extra features.
7. Do not mark the project resume-ready until every release gate in
   `docs/interview/ROADMAP.md` passes.

