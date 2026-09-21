"""Compare dense, BM25, and RRF hybrid chunk retrieval on identical cases.

This command calls the configured embedding model once per selected question but
does not invoke a chat model. Marker-derived relevance remains a screening proxy
unless the dataset contains validated human-selected exact chunk hashes.
"""

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from langchain_community.vectorstores import FAISS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controllable_rag.bm25 import BM25Index  # noqa: E402
from controllable_rag.config import get_settings  # noqa: E402
from controllable_rag.hybrid import reciprocal_rank_fusion  # noqa: E402
from controllable_rag.models import create_embedding_model  # noqa: E402
from evaluation.audit_dataset import normalize, read_cases, validate_cases  # noqa: E402
from evaluation.review_workflow import validate_materialized_reviews  # noqa: E402
from evaluation.run_retrieval_evaluation import (  # noqa: E402
    _case_relevant_keys,
    _document_key,
    marker_recall,
    ranked_relevance_metrics,
)

DEFAULT_DATASET = Path(__file__).with_name("dataset.jsonl")
DEFAULT_INDEX = PROJECT_ROOT / "chunks_vector_store"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "results"


def _mean(values):
    return round(statistics.fmean(values), 4) if values else None


def evaluate_ranking(documents, case, relevant_keys, ks):
    keys = [_document_key(document) for document in documents]
    relevance = [key in relevant_keys for key in keys]
    result = {}
    for k in ks:
        result.update(ranked_relevance_metrics(relevance, len(relevant_keys), k))
        marker_value, _ = marker_recall(
            [normalize(document.page_content) for document in documents[:k]],
            case["evidence"],
        )
        result[f"evidence_marker_recall@{k}"] = marker_value
    return result


def summarize(system_records, ks):
    output = {}
    for system, records in system_records.items():
        summary = {"cases": len(records)}
        for k in ks:
            for metric in ("hit", "precision", "recall", "mrr", "ndcg", "evidence_marker_recall"):
                field = f"{metric}@{k}"
                summary[field] = _mean([record[field] for record in records if record[field] is not None])
        summary["mean_query_latency_ms"] = _mean([record["query_latency_ms"] for record in records])
        output[system] = summary
    return output


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--trust-local-index", action="store_true")
    parser.add_argument("--ks", type=int, nargs="+", default=[1, 3, 5, 10])
    parser.add_argument("--candidate-pool", type=int, default=50)
    parser.add_argument("--rrf-constant", type=int, default=60)
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--require-human-approved", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.ks or any(k <= 0 for k in args.ks):
        raise SystemExit("--ks values must all be greater than zero")
    if args.candidate_pool < max(args.ks):
        raise SystemExit("--candidate-pool must be at least max(--ks)")
    if args.rrf_constant < 0:
        raise SystemExit("--rrf-constant must be non-negative")
    if not args.trust_local_index:
        raise SystemExit("Refusing to deserialize index.pkl without --trust-local-index")

    numbered_cases, parse_errors = read_cases(args.dataset)
    validation_errors, _ = validate_cases(numbered_cases, require_human_approved=args.require_human_approved)
    errors = [*parse_errors, *validation_errors]
    if errors:
        raise SystemExit("Dataset validation failed:\n- " + "\n- ".join(errors))
    cases = [case for _, case in numbered_cases if case["answerable"]]
    if args.ids:
        selected = set(args.ids)
        cases = [case for case in cases if case["id"] in selected]
        missing = selected - {case["id"] for case in cases}
        if missing:
            raise SystemExit("Selected IDs are absent or unanswerable: " + ", ".join(sorted(missing)))
    if args.limit is not None:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("No answerable evaluation cases selected")

    index_pickle = args.index_dir / "index.pkl"
    index_faiss = args.index_dir / "index.faiss"
    if not index_pickle.is_file() or not index_faiss.is_file():
        raise SystemExit(f"Missing FAISS index files under {args.index_dir}")
    index_pickle_hash = sha256(index_pickle.read_bytes()).hexdigest()
    settings = get_settings()
    store = FAISS.load_local(
        str(args.index_dir), create_embedding_model(settings), allow_dangerous_deserialization=True
    )
    corpus = list(store.docstore._dict.values())
    if args.require_human_approved:
        review_errors = validate_materialized_reviews(
            cases, index_pickle_hash, {_document_key(document) for document in corpus}
        )
        if review_errors:
            raise SystemExit("Formal retrieval review validation failed:\n- " + "\n- ".join(review_errors))

    bm25 = BM25Index([document.page_content for document in corpus])
    document_by_key = {}
    for document in corpus:
        document_by_key.setdefault(_document_key(document), document)
    system_records = {"dense": [], "bm25": [], "hybrid_rrf": []}
    case_records = []
    for case in cases:
        print(f"[{case['id']}] dense + BM25 + RRF", flush=True)
        dense_start = time.perf_counter()
        dense_pairs = store.similarity_search_with_score(case["question"], k=args.candidate_pool)
        dense_ms = (time.perf_counter() - dense_start) * 1000
        dense_documents = [document for document, _ in dense_pairs]

        bm25_start = time.perf_counter()
        bm25_indices = bm25.search(case["question"], args.candidate_pool)
        bm25_ms = (time.perf_counter() - bm25_start) * 1000
        bm25_documents = [corpus[index] for index in bm25_indices]

        fusion_start = time.perf_counter()
        fused = reciprocal_rank_fusion(
            [
                [_document_key(document) for document in dense_documents],
                [_document_key(document) for document in bm25_documents],
            ],
            limit=args.candidate_pool,
            rank_constant=args.rrf_constant,
        )
        hybrid_documents = [document_by_key[key] for key, _ in fused]
        fusion_ms = (time.perf_counter() - fusion_start) * 1000
        reviewed_keys = case.get("review", {}).get("gold_evidence_chunk_sha256")
        relevant_keys = set(reviewed_keys) if reviewed_keys is not None else _case_relevant_keys(corpus, case["evidence"])
        relevance_source = "human_exact_chunk_hashes" if reviewed_keys is not None else "marker_proxy"

        per_case = {"case_id": case["id"], "category": case["category"], "relevance_source": relevance_source, "systems": {}}
        for system, documents, latency in (
            ("dense", dense_documents, dense_ms),
            ("bm25", bm25_documents, bm25_ms),
            ("hybrid_rrf", hybrid_documents, dense_ms + bm25_ms + fusion_ms),
        ):
            metrics = evaluate_ranking(documents, case, relevant_keys, sorted(set(args.ks)))
            record = {
                **metrics,
                "query_latency_ms": round(latency, 4),
                "top_documents": [
                    {
                        "rank": rank,
                        "content_sha256": _document_key(document),
                        "page": document.metadata.get("page"),
                    }
                    for rank, document in enumerate(documents[: max(args.ks)], 1)
                ],
            }
            system_records[system].append(record)
            per_case["systems"][system] = record
        case_records.append(per_case)

    ks = sorted(set(args.ks))
    report = {
        "_metadata": {
            "created_at": datetime.now().astimezone().isoformat(),
            "dataset": str(args.dataset.resolve()),
            "dataset_sha256": sha256(args.dataset.read_bytes()).hexdigest(),
            "index_dir": str(args.index_dir.resolve()),
            "index_faiss_sha256": sha256(index_faiss.read_bytes()).hexdigest(),
            "index_pickle_sha256": index_pickle_hash,
            "embedding_model": settings.embedding_model,
            "embedding_dimensions": settings.embedding_dimensions,
            "faiss_index_type": type(store.index).__name__,
            "index_vectors": int(store.index.ntotal),
            "systems": ["dense", "bm25", "hybrid_rrf"],
            "candidate_pool": args.candidate_pool,
            "rrf_constant": args.rrf_constant,
            "bm25_k1": bm25.k1,
            "bm25_b": bm25.b,
            "ks": ks,
            "answerable_cases": len(cases),
            "relevance_definition": "human exact chunks when approved; otherwise marker-containing chunks as lexical proxy",
            "latency_scope": "single local sequential run; hybrid includes dense + BM25 + in-process fusion",
            "chat_model_calls": 0,
            "embedding_queries": len(cases),
        },
        "overall": summarize(system_records, ks),
        "cases": case_records,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"hybrid-retrieval-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2))
    print(f"Report: {output_path}")


if __name__ == "__main__":
    main()
