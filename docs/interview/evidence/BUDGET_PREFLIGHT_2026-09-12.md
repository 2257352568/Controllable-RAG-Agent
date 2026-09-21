# Chat budget preflight evidence — 2026-09-12

## Control contract

All Qwen chat clients created by the shared model factory use one request-boundary
adapter. Before each logical invocation it atomically reserves one invocation
slot and conservatively reserves UTF-8 input bytes, structured-output schema
bytes, configured maximum output tokens, and protocol headroom. It rejects calls
that cannot fit, then replaces the reservation with provider-reported actual
tokens after success. Missing usage metadata keeps the reservation committed and
marks accounting incomplete.

An outer callback independently records successful calls and tokens per graph
node and detects calls that bypass the factory. Embeddings remain outside this
chat budget. SDK-internal HTTP retries are not individually visible, so the
invocation cap is not yet an HTTP-attempt rate limiter.

## Frozen inputs

| Item | Value |
|---|---|
| Dataset SHA256 | `cacf6e16c83089df1f9780aa35045e01d081794a1ec6929a97d4ee383380e25a` |
| Case | `hp1-001` |
| Chat model | `qwen3.8-max` |
| Prompt version | `2026-09-12.2` |
| Enabled source | `chunks` |
| Minimum evidence | 1 |

## Real Qwen request-limit smoke

With `max_model_requests=1` and `max_total_tokens=8000`, anonymization completed
using 1 request and 395 tokens. The planner invocation was rejected before
dispatch. The result recorded `model_request_budget_exhausted`, enforcement
`pre_request`, 1 request started, 395 tokens committed, zero tokens reserved,
complete accounting, a rejected next-call reservation of 3,151 tokens, and
3.150 seconds latency.

## Real Qwen token-limit smoke

With `max_total_tokens=100`, the first structured call could not fit its
reservation and was rejected before dispatch. The result recorded
`token_budget_exhausted`, enforcement `pre_request`, 0 requests, 0 tokens, only
the deterministic initialize node, and 0.152 seconds latency.

## Interpretation boundary

These runs prove pre-dispatch control and reporting behavior. They do not select
a useful production budget or show answer quality. Conservative admission can
reject a call that might return a short response. Provider HTTP retry attempts
and embedding requests still require separate accounting and limiting.
