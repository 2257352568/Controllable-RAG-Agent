# Dense Retrieval Smoke Evidence — 2026-09-11

## Scope

This is a functional smoke evaluation of the Qwen dense **chunks** retriever,
not a formal resume metric. It uses the 11 answerable seed cases whose status is
`source_verified`; the two negative cases are excluded because a retriever always
returns neighbours and corpus absence still requires human review.

Relevance is a lexical proxy: a chunk is labelled relevant when it contains at
least one case evidence marker. The labels are not exhaustive human document
judgements, so the reported Recall@K, Precision@K, MRR and nDCG must be described
as **marker-proxy metrics**. `evidence_marker_recall@K` is the more direct measure
of how many independently listed evidence components occur in the retrieved set.

## Reproduction

```powershell
venv\Scripts\python.exe evaluation\audit_dataset.py `
  --dataset evaluation\dataset.jsonl `
  --trusted-corpus-index chunks_vector_store\index.pkl `
  --min-cases 13

venv\Scripts\python.exe evaluation\run_retrieval_evaluation.py `
  --dataset evaluation\dataset.jsonl `
  --ks 1 3 5 10 `
  --trust-local-index
```

`--trust-local-index` is deliberately required because LangChain's persisted
FAISS docstore uses pickle and must never be loaded from an untrusted source.

## Frozen inputs

| Item | Value |
|---|---|
| Run time | 2026-09-11 23:49:31 +08:00 |
| Dataset SHA256 | `cacf6e16c83089df1f9780aa35045e01d081794a1ec6929a97d4ee383380e25a` |
| FAISS binary SHA256 | `dab1276f8aed2a84ee6afe3a4db11f9e7420cf40a86661b8a9c728d17fea5b74` |
| Docstore pickle SHA256 | `b2f74c7eace8a8517d27e027cfea18e50098febec4ed2af6f5af10a7f9aaa26b` |
| Embedding | `text-embedding-v4`, 1536 dimensions |
| FAISS index | `IndexFlatL2`, 618 vectors |
| Cases | 11 answerable seed cases |

## Results

| Metric | K=1 | K=3 | K=5 | K=10 |
|---|---:|---:|---:|---:|
| Marker-proxy Hit@K | 0.9091 | 0.9091 | 1.0000 | 1.0000 |
| Marker-proxy Precision@K | 0.9091 | 0.5151 | 0.4364 | 0.3091 |
| Marker-proxy Recall@K | 0.3120 | 0.3673 | 0.5254 | 0.6173 |
| Marker-proxy MRR@K | 0.9091 | 0.9091 | 0.9318 | 0.9318 |
| Marker-proxy nDCG@K | 0.9091 | 0.7023 | 0.7000 | 0.6859 |
| Evidence marker recall@K | 0.7727 | 0.8182 | 0.9091 | 0.9091 |

Single-hop marker recall reached 1.0 at K=3. Multi-hop marker recall was only
0.4444 at K=1 and 0.7778 at K=5/K=10. This is evidence for the expected
quality/noise trade-off: increasing K recovered more multi-hop evidence, while
overall proxy precision fell from 0.9091 at K=1 to 0.3091 at K=10. The sample is
too small and incompletely reviewed to select a production K from these numbers.

## Failure and label audit

The first run reported `hp1-002` and `hp1-011` as Top-10 misses. Inspection
showed both were label errors:

- `hp1-002` Top-1 directly said “The Seeker. That's you”, while the old marker
  used a different, indirect sentence.
- `hp1-011` Top-1 contained Quirrell's admission, while an old marker came from
  Harry's earlier incorrect suspicion of Snape.

The markers were corrected against trusted local source pages and the full
dataset evidence audit passed before rerunning. This changed the dataset hash and
therefore invalidates comparison with results produced from the old hash. The
repair is data-quality work, not a retrieval-model improvement.

Remaining misses are also informative: `hp1-008` and `hp1-011` each lack some
multi-part evidence at K=10. A formal retrieval benchmark still needs reviewers
to select exact relevant chunk hashes instead of treating every occurrence of a
marker as relevant.
