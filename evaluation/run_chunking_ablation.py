"""Screen chunking configurations with offline BM25 over the current corpus snapshot."""

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controllable_rag.bm25 import BM25Index
from evaluation.audit_dataset import normalize, read_cases, validate_cases
from evaluation.audit_ingestion import exact_suffix_prefix_overlap, load_documents
from evaluation.run_retrieval_evaluation import marker_recall, ranked_relevance_metrics

DEFAULT_INDEX = PROJECT_ROOT / "chunks_vector_store" / "index.pkl"
DEFAULT_DATASET = PROJECT_ROOT / "evaluation" / "dataset.jsonl"


def reconstruct_pages(chunk_documents):
    grouped = defaultdict(list)
    for document in chunk_documents:
        grouped[document.metadata.get("page")].append(str(document.page_content))
    pages = []
    for page, texts in sorted(grouped.items(), key=lambda item: (item[0] is None, item[0])):
        merged = texts[0]
        for text in texts[1:]:
            overlap = exact_suffix_prefix_overlap(merged, text, maximum=min(len(merged), len(text)))
            merged += text[overlap:]
        pages.append(Document(page_content=merged, metadata={"page": page, "source": "reconstructed-current-index"}))
    return pages


def split_pages(pages, chunk_size, overlap):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=overlap, length_function=len
    )
    return splitter.split_documents(pages)


def reconstruction_fidelity(original, rebuilt):
    def digest(document):
        return sha256(
            str(document.page_content).encode("utf-8", errors="replace")
        ).hexdigest()

    original_hashes = [digest(document) for document in original]
    rebuilt_hashes = [digest(document) for document in rebuilt]
    positional_matches = sum(
        left == right for left, right in zip(original_hashes, rebuilt_hashes)
    )
    unique_original = set(original_hashes)
    return {
        "original_documents": len(original_hashes),
        "rebuilt_documents": len(rebuilt_hashes),
        "positional_exact_matches": positional_matches,
        "positional_match_rate": round(
            positional_matches / max(len(original_hashes), len(rebuilt_hashes)), 4
        ),
        "unique_original_hash_coverage": round(
            len(unique_original & set(rebuilt_hashes)) / len(unique_original), 4
        ),
    }


def evaluate_configuration(pages, cases, chunk_size, overlap, ks):
    started = time.perf_counter()
    documents = split_pages(pages, chunk_size, overlap)
    texts = [str(document.page_content) for document in documents]
    index = BM25Index(texts)
    build_seconds = time.perf_counter() - started
    per_case = []
    query_seconds = []
    max_k = max(ks)
    for case in cases:
        query_started = time.perf_counter()
        ranked_indices = index.search(case["question"], max_k)
        query_seconds.append(time.perf_counter() - query_started)
        ranked_texts = [normalize(texts[index]) for index in ranked_indices]
        normalized_markers = [normalize(marker) for marker in case["evidence"]]
        relevant_keys = {
            index for index, text in enumerate(texts)
            if any(marker in normalize(text) for marker in normalized_markers)
        }
        relevance = [index in relevant_keys for index in ranked_indices]
        result = {"case_id": case["id"], "category": case["category"]}
        for k in ks:
            result.update(ranked_relevance_metrics(relevance, len(relevant_keys), k))
            recall, _ = marker_recall(ranked_texts[:k], case["evidence"])
            result[f"evidence_marker_recall@{k}"] = recall
        per_case.append(result)

    summary = {
        "chunk_size": chunk_size,
        "chunk_overlap": overlap,
        "documents": len(documents),
        "mean_characters": round(statistics.fmean(map(len, texts)), 2),
        "p95_characters": sorted(map(len, texts))[int(0.95 * (len(texts) - 1))],
        "build_seconds": round(build_seconds, 6),
        "mean_query_ms": round(statistics.fmean(query_seconds) * 1000, 4),
    }
    for k in ks:
        for metric in ("hit", "precision", "recall", "mrr", "ndcg", "evidence_marker_recall"):
            field = f"{metric}@{k}"
            values = [record[field] for record in per_case if record.get(field) is not None]
            summary[field] = round(statistics.fmean(values), 4) if values else None
    return summary, per_case


def parse_config(value):
    try:
        size, overlap = (int(part) for part in value.split(":", 1))
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError("configuration must be SIZE:OVERLAP") from error
    if size <= 0 or overlap < 0 or overlap >= size:
        raise argparse.ArgumentTypeError("require SIZE > OVERLAP >= 0")
    return size, overlap


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--configs", nargs="+", type=parse_config, default=[(500, 100), (750, 150), (1000, 200), (1250, 250), (1500, 300)])
    parser.add_argument("--ks", nargs="+", type=int, default=[1, 3, 5, 10])
    parser.add_argument("--trust-local-index", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.trust_local_index:
        raise SystemExit("Refusing to deserialize index.pkl without --trust-local-index")
    if any(k <= 0 for k in args.ks):
        raise SystemExit("all K values must be positive")
    numbered, parse_errors = read_cases(args.dataset)
    validation_errors, _ = validate_cases(numbered)
    if parse_errors or validation_errors:
        raise SystemExit("Dataset validation failed: " + "; ".join([*parse_errors, *validation_errors]))
    cases = [case for _, case in numbered if case["answerable"]]
    original_chunks = load_documents(args.index)
    pages = reconstruct_pages(original_chunks)
    baseline_rebuilt = split_pages(pages, 1000, 200)
    page_payload = json.dumps(
        [{"page": page.metadata.get("page"), "content": page.page_content} for page in pages],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    configurations = []
    case_results = {}
    for chunk_size, overlap in args.configs:
        label = f"{chunk_size}:{overlap}"
        print(f"[{label}] offline BM25", flush=True)
        summary, details = evaluate_configuration(
            pages, cases, chunk_size, overlap, sorted(set(args.ks))
        )
        configurations.append(summary)
        case_results[label] = details
    report = {
        "_metadata": {
            "created_at": datetime.now().astimezone().isoformat(),
            "dataset": str(args.dataset.resolve()),
            "dataset_sha256": sha256(args.dataset.read_bytes()).hexdigest(),
            "source_index": str(args.index.resolve()),
            "source_index_sha256": sha256(args.index.read_bytes()).hexdigest(),
            "reconstructed_pages": len(pages),
            "reconstructed_corpus_sha256": sha256(page_payload).hexdigest(),
            "baseline_reconstruction_fidelity": reconstruction_fidelity(
                original_chunks, baseline_rebuilt
            ),
            "retriever": "deterministic BM25 k1=1.5 b=0.75",
            "relevance": "evidence-marker lexical proxy",
            "purpose": "offline screening only; does not establish dense-Qwen optimum",
        },
        "configurations": configurations,
        "cases": case_results,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps(configurations, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
