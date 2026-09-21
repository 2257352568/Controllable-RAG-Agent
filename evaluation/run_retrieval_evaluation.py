"""Evaluate dense chunk retrieval without invoking a chat model.

Relevance is derived from human-reviewable evidence markers in the dataset. This
is a lexical proxy over the fixed local corpus, not a claim that every relevant
document has been exhaustively annotated.
"""

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from langchain_community.vectorstores import FAISS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controllable_rag.config import get_settings  # noqa: E402
from controllable_rag.models import create_embedding_model  # noqa: E402
from evaluation.audit_dataset import normalize, read_cases, validate_cases  # noqa: E402
from evaluation.review_workflow import validate_materialized_reviews  # noqa: E402

DEFAULT_DATASET = Path(__file__).with_name("dataset.jsonl")
DEFAULT_INDEX = PROJECT_ROOT / "chunks_vector_store"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "results"


def _mean(values):
    return round(statistics.fmean(values), 4) if values else None


def ranked_relevance_metrics(relevance, total_relevant, k):
    """Return binary retrieval metrics at k for a ranked relevance sequence."""
    ranked = [int(bool(value)) for value in relevance[:k]]
    relevant_retrieved = sum(ranked)
    first_rank = next((rank for rank, value in enumerate(ranked, 1) if value), None)
    dcg = sum(value / math.log2(rank + 1) for rank, value in enumerate(ranked, 1))
    ideal_count = min(int(total_relevant), k)
    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
    return {
        f"hit@{k}": float(relevant_retrieved > 0),
        f"precision@{k}": round(relevant_retrieved / k, 4),
        f"recall@{k}": round(
            relevant_retrieved / total_relevant, 4
        ) if total_relevant else None,
        f"mrr@{k}": round(1 / first_rank, 4) if first_rank else 0.0,
        f"ndcg@{k}": round(dcg / idcg, 4) if idcg else None,
    }


def marker_recall(retrieved_texts, markers):
    """Fraction of independently labelled evidence markers covered by retrieval."""
    if not markers:
        return None, []
    hits = []
    for marker in markers:
        normalized_marker = normalize(marker)
        hits.append(any(normalized_marker in text for text in retrieved_texts))
    return round(sum(hits) / len(hits), 4), hits


def _document_key(document):
    content = str(document.page_content)
    return sha256(content.encode("utf-8", errors="replace")).hexdigest()


def _case_relevant_keys(corpus_documents, markers):
    normalized_markers = [normalize(marker) for marker in markers]
    return {
        _document_key(document)
        for document in corpus_documents
        if any(marker in normalize(document.page_content) for marker in normalized_markers)
    }


def evaluate_case(store, corpus_documents, case, ks):
    max_k = max(ks)
    ranked = store.similarity_search_with_score(case["question"], k=max_k)
    reviewed_keys = case.get("review", {}).get("gold_evidence_chunk_sha256")
    relevant_keys = (
        set(reviewed_keys)
        if reviewed_keys is not None
        else _case_relevant_keys(corpus_documents, case["evidence"])
    )
    retrieved_keys = [_document_key(document) for document, _ in ranked]
    relevance = [key in relevant_keys for key in retrieved_keys]
    record = {
        "case_id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "gold_relevant_documents": len(relevant_keys),
        "relevance_source": "human_exact_chunk_hashes" if reviewed_keys is not None else "marker_proxy",
        "retrieved": [
            {
                "rank": rank,
                "page": document.metadata.get("page"),
                "distance": round(float(distance), 6),
                "relevant": relevance[rank - 1],
                "content_sha256": retrieved_keys[rank - 1],
            }
            for rank, (document, distance) in enumerate(ranked, 1)
        ],
    }
    if reviewed_keys is None:
        record["marker_proxy_relevant_documents"] = len(relevant_keys)
    for k in ks:
        record.update(ranked_relevance_metrics(relevance, len(relevant_keys), k))
        marker_value, marker_hits = marker_recall(
            [normalize(document.page_content) for document, _ in ranked[:k]],
            case["evidence"],
        )
        record[f"evidence_marker_recall@{k}"] = marker_value
        record[f"evidence_marker_hits@{k}"] = marker_hits
    return record


def summarize(records, ks):
    def group_summary(items):
        summary = {"cases": len(items)}
        for k in ks:
            for metric in (
                "hit",
                "precision",
                "recall",
                "mrr",
                "ndcg",
                "evidence_marker_recall",
            ):
                field = f"{metric}@{k}"
                summary[field] = _mean(
                    [item[field] for item in items if item.get(field) is not None]
                )
        return summary

    by_category = defaultdict(list)
    for record in records:
        by_category[record["category"]].append(record)
    return {
        "overall": group_summary(records),
        "by_category": {
            category: group_summary(items)
            for category, items in sorted(by_category.items())
        },
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX)
    parser.add_argument(
        "--trust-local-index",
        action="store_true",
        help="Acknowledge that index.pkl is trusted; pickle can execute code.",
    )
    parser.add_argument("--ks", type=int, nargs="+", default=[1, 3, 5, 10])
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--require-human-approved", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.ks or any(k <= 0 for k in args.ks):
        raise SystemExit("--ks values must all be greater than zero")
    ks = sorted(set(args.ks))
    numbered_cases, parse_errors = read_cases(args.dataset)
    validation_errors, _ = validate_cases(
        numbered_cases, require_human_approved=args.require_human_approved
    )
    errors = [*parse_errors, *validation_errors]
    if errors:
        raise SystemExit("Dataset validation failed:\n- " + "\n- ".join(errors))
    all_cases = [case for _, case in numbered_cases]
    negative_case_count = sum(not case["answerable"] for case in all_cases)
    cases = [case for case in all_cases if case["answerable"]]
    if args.ids:
        selected = set(args.ids)
        cases = [case for case in cases if case["id"] in selected]
        missing = selected - {case["id"] for case in cases}
        if missing:
            raise SystemExit(
                "Selected IDs are absent or unanswerable: " + ", ".join(sorted(missing))
            )
    if args.limit is not None:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("No answerable evaluation cases selected")
    if not args.trust_local_index:
        raise SystemExit(
            "Refusing to deserialize index.pkl without --trust-local-index; "
            "only load an index created by this project or another trusted source."
        )

    settings = get_settings()
    index_pickle = args.index_dir / "index.pkl"
    index_faiss = args.index_dir / "index.faiss"
    if not index_pickle.is_file() or not index_faiss.is_file():
        raise SystemExit(f"Missing FAISS index files under {args.index_dir}")
    index_pickle_sha256 = sha256(index_pickle.read_bytes()).hexdigest()
    store = FAISS.load_local(
        str(args.index_dir),
        create_embedding_model(settings),
        allow_dangerous_deserialization=True,
    )
    corpus_documents = list(store.docstore._dict.values())
    if args.require_human_approved:
        known_chunk_hashes = {_document_key(document) for document in corpus_documents}
        review_errors = validate_materialized_reviews(
            cases, index_pickle_sha256, known_chunk_hashes
        )
        if review_errors:
            raise SystemExit(
                "Formal retrieval review validation failed:\n- "
                + "\n- ".join(review_errors)
            )
    records = []
    for case in cases:
        print(f"[{case['id']}] dense chunks", flush=True)
        records.append(evaluate_case(store, corpus_documents, case, ks))

    report = summarize(records, ks)
    report["_metadata"] = {
        "created_at": datetime.now().astimezone().isoformat(),
        "dataset": str(args.dataset.resolve()),
        "dataset_sha256": sha256(args.dataset.read_bytes()).hexdigest(),
        "index_dir": str(args.index_dir.resolve()),
        "index_faiss_sha256": sha256(index_faiss.read_bytes()).hexdigest(),
        "index_pickle_sha256": index_pickle_sha256,
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": settings.embedding_dimensions,
        "faiss_index_type": type(store.index).__name__,
        "index_vectors": int(store.index.ntotal),
        "ks": ks,
        "answerable_cases": len(cases),
        "excluded_negative_cases": negative_case_count,
        "relevance_definition": (
            "human-selected exact gold supporting chunk hashes for formal reviewed cases; "
            "otherwise document contains >=1 labelled evidence marker as a lexical proxy"
        ),
        "distance_strategy": str(store.distance_strategy),
        "score_semantics": "raw FAISS score; ranking follows the configured distance strategy",
    }
    report["cases"] = records
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / (
        f"retrieval-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2))
    print(f"Report: {output_path}")


if __name__ == "__main__":
    main()
