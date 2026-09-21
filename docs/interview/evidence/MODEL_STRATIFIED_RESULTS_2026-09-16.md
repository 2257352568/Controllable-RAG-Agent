# Model-stratified evaluation after quota exhaustion

## Provenance and scope

The frozen 52-case human-approved dataset has SHA256
`5a713470ef679196c07d92bb709ec6a49319eeceeff4f096b2bc389142ea3bf3`.
Both experiments used `text-embedding-v4` (1536 dimensions), `chunks` retrieval
for both RAG systems, and independent `deepseek-v4-pro-0813` judging. Neither
stratum is a substitute for a single-model 52-case formal release result.

| Stratum | Generator | Cases | Runs | Details SHA256 |
| --- | --- | ---: | ---: | --- |
| A | `qwen3.7-flash` | `hp1-001`–`hp1-039` | 351 | `90ac83d0261b41ff38b84571464afe27853c3b74f5cca58c9fd2c14bf86ee45e` |
| B | `qwen3.7-flash-2026-07-15` | `hp1-040`–`hp1-052` | 117 | `5bf4f685573a707a1020125270298c777c07c35a608b03109c6bbb7787156df7` |

Stratum A is extracted without changing records from the complete run in
`evaluation/results/formal-run-20260916-v2/`. Its subsequent quota-403 records
are excluded from this stratum, not relabeled as successful. Stratum B is the
separate `--ids` run in `evaluation/results/snapshot-remaining-20260916/`.
Its 117 unique case/system/repetition slots are complete, and its saved details
hash matches its summary. The executable quality gate still fails.

## Descriptive results

Metrics are computed only within each model stratum. `answer_hit` and judge
metrics use the project's existing successful-run denominator; consult error
rate alongside them. These are not a pooled 52-case score.

| Stratum | System | Success/runs | Error rate | Answer hit | Judge correctness | Citation evidence recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A | Direct | 117/117 | 0.0% | 54.70% | 63.42% | N/A |
| A | Naive RAG | 117/117 | 0.0% | 55.56% | 62.56% | 57.66% |
| A | Agentic RAG | 103/117 | 11.97% | 27.18% | 41.07% | 32.15% |
| B | Direct | 39/39 | 0.0% | 41.03% | 49.23% | N/A |
| B | Naive RAG | 39/39 | 0.0% | 41.03% | 77.18% | 50.00% |
| B | Agentic RAG | 25/39 | 35.90% | 8.00% | 40.00% | 20.00% |

Within A, the paired case-level bootstrap includes 31 complete/error-free
Agent–naive pairs for answer hit and judge correctness. It favors naive RAG:
answer-hit delta (naive minus Agent) `+0.322581`, 95% CI
`[0.129032, 0.516129]`; judge-correctness delta `+0.246237`, 95% CI
`[0.068817, 0.427957]`. This is a negative result for the current Agent
architecture, not evidence of improvement.

The same A records show a large descriptive cost gap on successful runs only:
Agent `103` runs averaged `18.93` chat requests, `7,929` chat tokens and
`32.53` seconds; naive RAG `117` runs averaged `1.00` request, `319` tokens
and `1.68` seconds. The denominators differ because 14 Agent runs errored,
and embedding usage is not included in chat tokens. These means illustrate
complexity and cost, not a paired causal estimate or a valid pooled result.

## Failure analysis and interview lesson

- A has 14 Agent errors before quota exhaustion: 8 graph-recursion-limit,
  2 structured-output 400, 2 provider 429, and 2 observed-node errors.
- B has 14 Agent errors: 12 graph-recursion-limit and 2 observed-node errors.
  Of its 25 completed Agent runs, 18 terminated at the token budget, 5 with
  grounding failure, and only 2 answered. This makes the current Agent
  especially ineffective on the harder tail, which contains 6 adversarial,
  4 multi-hop, and 3 unanswerable cases.
- The model change was caused by independent free-quota exhaustion, not by a
  pre-registered model-comparison design. The strata differ in both model and
  case difficulty; comparing A against B as if model were the only variable
  would be confounded.

The next engineering focus is to trace repeated planning/retrieval cycles,
ensure budget exhaustion produces a controlled termination distinct from a knowledge-based abstention, and test the
general control-flow fix on new or held-out cases. Do not lower the protocol
thresholds or write these exploratory metrics as a resume win.

The 52 reviewed cases are now a development regression set as well: these
failures informed the recursion-limit and final-step replanning changes.
Rerunning them can test whether those changes fix known cases, but it cannot
serve as an independent estimate of generalization. A future resume-quality
claim needs a separately reviewed, previously unseen holdout after the
implementation and decision thresholds are locked.
