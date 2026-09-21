# Runtime trace persistence smoke — 2026-09-12

## Scope

This smoke validates local operational trace persistence. It does not establish
a production audit log, distributed tracing backend, or cryptographic
authenticity.

## Configuration and run

The Agent ran case `hp1-001` on `qwen3.8-max` with `chunks` enabled,
`max_total_tokens=100`, and trace persistence enabled. Token admission stopped
the first model call before dispatch, which gives a deterministic termination
path.

The result generated trace ID
`b93426c8-7e41-4551-b281-8e4258c4b3b2`. The standalone verifier returned:

```text
valid=true reason=ok
```

The payload checksum was
`562033c87d54c5a37247d50a5b181ed47f315597c9be871c2a6e132cdcde2461`.
It recorded `token_budget_exhausted`, `pre_request`, 0 requests, 0 tokens, the
initialize/budget events, policy configuration, and reservation diagnostics.

## Privacy and failure behavior

Persistence uses an explicit field allowlist. A search of the trace directory
found none of the question text, `Hogwarts`, reference answer, prompt/context
test sentinels, or provider error sentinel. Tests also prove:

- prompts, questions, contexts, answers and arbitrary event/error fields are
  excluded;
- each UUID filename is write-once within the local directory;
- writes publish a complete temporary file atomically;
- a modified payload fails checksum verification;
- persistence failure leaves the Agent terminal result intact and exposes only
  the safe exception type.
- a node exception persists the partial trace with only node, duration and
  exception type, then still propagates the original failure to the caller.

## Reproduction

```powershell
venv\Scripts\python.exe evaluation\run_evaluation.py `
  --systems agentic-rag --ids hp1-001 `
  --enabled-sources chunks --min-evidence-records 1 `
  --max-steps 1 --max-model-requests 12 --max-total-tokens 100 `
  --retries 0 --persist-traces

venv\Scripts\python.exe evaluation\verify_trace.py `
  runtime_traces\<trace-id>.json
```

`runtime_traces/` is excluded from Git and Docker build context.

## Security boundary

The SHA256 is a self-consistency checksum stored beside the payload. An attacker
who can rewrite the file can also recompute it. Authentic audit evidence needs a
separately protected HMAC/signing key or an append-only external backend. Local
files also lack cross-process querying, retention policy, access control and
distributed trace propagation.
