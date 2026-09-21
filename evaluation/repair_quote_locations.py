"""Recover quote page metadata from the trusted chunk index without model calls."""

from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
from collections import Counter
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controllable_rag.index_manifest import write_index_manifest
from evaluation.audit_ingestion import load_documents
from evaluation.run_chunking_ablation import reconstruct_pages

DEFAULT_CHUNKS = PROJECT_ROOT / "chunks_vector_store" / "index.pkl"
DEFAULT_QUOTES = PROJECT_ROOT / "book_quotes_vectorstore" / "index.pkl"
MATCH_METHOD = "normalized_exact_match_against_reconstructed_chunks"


def normalize_whitespace(value) -> str:
    return " ".join(str(value).split())


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def locate_quote_pages(quotes, pages) -> list[list[int]]:
    normalized_pages = [
        (int(document.metadata["page"]), normalize_whitespace(document.page_content))
        for document in pages
    ]
    return [
        [
            page
            for page, text in normalized_pages
            if normalize_whitespace(quote.page_content) in text
        ]
        for quote in quotes
    ]


def enrich_quote_documents(quotes, matches) -> dict:
    counts = Counter()
    for document, pages in zip(quotes, matches, strict=True):
        metadata = dict(document.metadata or {})
        metadata.pop("page", None)
        metadata.pop("location_candidates", None)
        if len(pages) == 1:
            metadata["page"] = pages[0]
            status = "unique"
        elif pages:
            metadata["location_candidates"] = pages
            status = "ambiguous"
        else:
            status = "missing"
        metadata["location_match_status"] = status
        metadata["location_provenance"] = MATCH_METHOD
        # These documents were pickled by an older LangChain/Pydantic version.
        # Reassigning a model field can fail because legacy private state does not
        # satisfy Pydantic v2, while the already-loaded metadata dict is mutable.
        document.metadata.clear()
        document.metadata.update(metadata)
        counts[status] += 1
    total = len(quotes)
    return {
        "documents": total,
        "unique": counts["unique"],
        "ambiguous": counts["ambiguous"],
        "missing": counts["missing"],
        "page_coverage": round(counts["unique"] / total, 6) if total else 0.0,
        "match_method": MATCH_METHOD,
    }


def load_quote_store(path: Path):
    with path.open("rb") as stream:
        docstore, index_to_docstore_id = pickle.load(stream)  # noqa: S301
    documents = [
        docstore.search(index_to_docstore_id[position])
        for position in range(len(index_to_docstore_id))
    ]
    return docstore, index_to_docstore_id, documents


def write_quote_store(path: Path, docstore, index_to_docstore_id) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as stream:
            pickle.dump(
                (docstore, index_to_docstore_id), stream, protocol=pickle.HIGHEST_PROTOCOL
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--quotes", type=Path, default=DEFAULT_QUOTES)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--trust-local-index", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.trust_local_index:
        raise SystemExit("Refusing to deserialize index.pkl without --trust-local-index")

    chunk_path = args.chunks.resolve()
    quote_path = args.quotes.resolve()
    chunks = load_documents(chunk_path)
    docstore, index_to_docstore_id, quotes = load_quote_store(quote_path)
    pages = reconstruct_pages(chunks)
    matches = locate_quote_pages(quotes, pages)
    report = enrich_quote_documents(quotes, matches)
    report.update({
        "chunk_pages": len(pages),
        "written": bool(args.write),
        "chunk_index_pickle_sha256": file_digest(chunk_path),
        "quote_index_pickle_sha256_before": file_digest(quote_path),
        "ambiguous_records": [
            {
                "quote_index": index,
                "candidate_pages": candidate_pages,
            }
            for index, candidate_pages in enumerate(matches)
            if len(candidate_pages) > 1
        ],
    })
    if args.write:
        root = chunk_path.parent.parent
        if quote_path.parent.parent != root:
            raise SystemExit("chunk and quote indexes must share one project root when writing")
        manifest_path = root / "index_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        embedding = manifest["embedding"]
        write_quote_store(quote_path, docstore, index_to_docstore_id)
        write_index_manifest(root, embedding["model"], embedding["dimensions"])
        report["quote_index_pickle_sha256_after"] = file_digest(quote_path)
        report["index_manifest_sha256_after"] = file_digest(manifest_path)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if report["missing"] == 0 else 1)


if __name__ == "__main__":
    main()
