"""Audit immutable ingestion facts and current FAISS docstore distributions."""

import argparse
import json
import pickle
import statistics
from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTEBOOK = PROJECT_ROOT / "sophisticated_rag_agent_harry_potter.ipynb"
STORE_NAMES = (
    "chunks_vector_store",
    "chapter_summaries_vector_store",
    "book_quotes_vectorstore",
)


def percentile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def exact_suffix_prefix_overlap(left, right, maximum=1000):
    left, right = str(left), str(right)
    for size in range(min(maximum, len(left), len(right)), 0, -1):
        if left[-size:] == right[:size]:
            return size
    return 0


def document_statistics(documents):
    lengths = [len(str(document.page_content)) for document in documents]
    metadata_fields = sorted({key for document in documents for key in (document.metadata or {})})
    metadata_fields = sorted({key for document in documents for key in (document.metadata or {})})
    metadata_coverage = {
        key: sum((document.metadata or {}).get(key) is not None for document in documents)
        for key in metadata_fields
    }
    return {
        "documents": len(documents),
        "characters": {
            "min": min(lengths),
            "mean": round(statistics.fmean(lengths), 2),
            "p50": round(percentile(lengths, 0.5), 2),
            "p95": round(percentile(lengths, 0.95), 2),
            "max": max(lengths),
        },
        "metadata_fields": metadata_fields,
        "metadata_coverage": metadata_coverage,
    }


def chunk_overlap_statistics(documents, maximum):
    overlaps = [
        exact_suffix_prefix_overlap(left.page_content, right.page_content, maximum)
        for left, right in zip(documents, documents[1:])
        if left.metadata.get("page") == right.metadata.get("page")
    ]
    return {
        "same_page_pairs": len(overlaps),
        "zero_overlap_pairs": sum(value == 0 for value in overlaps),
        "min": min(overlaps) if overlaps else None,
        "mean": round(statistics.fmean(overlaps), 2) if overlaps else None,
        "p50": round(percentile(overlaps, 0.5), 2) if overlaps else None,
        "p95": round(percentile(overlaps, 0.95), 2) if overlaps else None,
        "max": max(overlaps) if overlaps else None,
    }


def quote_location_statistics(documents):
    statuses = Counter(
        (document.metadata or {}).get("location_match_status") for document in documents
    )
    invalid = 0
    for document in documents:
        metadata = document.metadata or {}
        status = metadata.get("location_match_status")
        page = metadata.get("page")
        candidates = metadata.get("location_candidates")
        provenance = metadata.get("location_provenance")
        valid = bool(provenance) and (
            (status == "unique" and page is not None and candidates is None)
            or (
                status == "ambiguous"
                and page is None
                and isinstance(candidates, list)
                and all(isinstance(candidate, int) for candidate in candidates)
                and len(set(candidates)) >= 2
            )
            or (status == "missing" and page is None and candidates is None)
        )
        invalid += not valid
    total = len(documents)
    return {
        "documents": total,
        "unique": statuses["unique"],
        "ambiguous": statuses["ambiguous"],
        "missing": statuses["missing"],
        "invalid": invalid,
        "page_coverage": round(statuses["unique"] / total, 6) if total else 0.0,
    }


def load_documents(index_pickle):
    with index_pickle.open("rb") as stream:
        docstore, index_to_docstore_id = pickle.load(stream)  # noqa: S301
    return [
        docstore.search(index_to_docstore_id[position])
        for position in range(len(index_to_docstore_id))
    ]


def notebook_sources(path):
    notebook = json.loads(path.read_text(encoding="utf-8"))
    return "\n".join(
        "".join(cell.get("source", [])) for cell in notebook.get("cells", [])
    )


def build_report(root, notebook_path, expected_chunk_size=1000, expected_overlap=200):
    errors = []
    source = notebook_sources(notebook_path)
    expected_definition = f"def encode_book(path, chunk_size={expected_chunk_size}, chunk_overlap={expected_overlap})"
    expected_call = f"encode_book(hp_pdf_path, chunk_size={expected_chunk_size}, chunk_overlap={expected_overlap})"
    if expected_definition not in source:
        errors.append("upstream notebook encode_book defaults do not match expected parameters")
    if expected_call not in source:
        errors.append("upstream notebook index construction call does not match expected parameters")

    stores = {}
    chunk_documents = None
    quote_locations = None
    for name in STORE_NAMES:
        index_pickle = root / name / "index.pkl"
        index_faiss = root / name / "index.faiss"
        if not index_pickle.is_file() or not index_faiss.is_file():
            errors.append(f"missing index files for {name}")
            continue
        documents = load_documents(index_pickle)
        stats = document_statistics(documents)
        stats["index_pickle_sha256"] = sha256(index_pickle.read_bytes()).hexdigest()
        stats["index_faiss_sha256"] = sha256(index_faiss.read_bytes()).hexdigest()
        stores[name] = stats
        if name == "chunks_vector_store":
            chunk_documents = documents
            if stats["characters"]["max"] > expected_chunk_size:
                errors.append("chunk document exceeds configured chunk_size")
            if "page" not in stats["metadata_fields"]:
                errors.append("chunk documents lack page metadata")
        elif name == "book_quotes_vectorstore":
            quote_locations = quote_location_statistics(documents)
            if quote_locations["missing"]:
                errors.append("quote documents have missing source locations")
            if quote_locations["invalid"]:
                errors.append("quote location metadata violates the fail-closed contract")

    overlap_stats = (
        chunk_overlap_statistics(chunk_documents, expected_overlap)
        if chunk_documents else None
    )
    if overlap_stats and overlap_stats["max"] > expected_overlap:
        errors.append("observed exact overlap exceeds configured maximum")
    if overlap_stats and overlap_stats["same_page_pairs"] and overlap_stats["zero_overlap_pairs"]:
        errors.append("same-page adjacent chunks unexpectedly have zero exact overlap")
    return {
        "created_at": datetime.now().astimezone().isoformat(),
        "source_notebook": str(notebook_path.resolve()),
        "source_notebook_sha256": sha256(notebook_path.read_bytes()).hexdigest(),
        "chunking_contract": {
            "splitter": "RecursiveCharacterTextSplitter",
            "length_function": "len (characters)",
            "configured_chunk_size": expected_chunk_size,
            "configured_chunk_overlap": expected_overlap,
            "ownership": "upstream configuration retained by local Qwen re-embedding",
        },
        "stores": stores,
        "chunks_exact_overlap": overlap_stats,
        "quote_locations": quote_locations,
        "errors": errors,
        "valid": not errors,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--notebook", type=Path, default=DEFAULT_NOTEBOOK)
    parser.add_argument("--expected-chunk-size", type=int, default=1000)
    parser.add_argument("--expected-overlap", type=int, default=200)
    parser.add_argument("--trust-local-index", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.trust_local_index:
        raise SystemExit("Refusing to deserialize index.pkl without --trust-local-index")
    if args.expected_chunk_size <= 0 or args.expected_overlap < 0:
        raise SystemExit("chunk size must be positive and overlap non-negative")
    report = build_report(
        args.root.resolve(), args.notebook.resolve(),
        args.expected_chunk_size, args.expected_overlap,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
