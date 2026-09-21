"""Safe hash manifest for bundled vector indexes."""

from __future__ import annotations

import json
import os
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

INDEX_MANIFEST_SCHEMA = "2026-09-13.1"
INDEX_MANIFEST_NAME = "index_manifest.json"
STORE_DIRECTORIES = {
    "chunks": "chunks_vector_store",
    "summaries": "chapter_summaries_vector_store",
    "quotes": "book_quotes_vectorstore",
}
INDEX_FILES = ("index.faiss", "index.pkl")


def file_sha256(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def build_index_manifest(root: Path, embedding_model: str, dimensions: int) -> dict:
    root = Path(root).resolve()
    stores = {}
    for source, directory_name in STORE_DIRECTORIES.items():
        directory = root / directory_name
        stores[source] = {
            "files": {
                name: {
                    "size_bytes": (directory / name).stat().st_size,
                    "sha256": file_sha256(directory / name),
                }
                for name in INDEX_FILES
            }
        }
    return {
        "schema_version": INDEX_MANIFEST_SCHEMA,
        "embedding": {
            "model": str(embedding_model),
            "dimensions": int(dimensions),
        },
        "stores": stores,
    }


def write_index_manifest(root: Path, embedding_model: str, dimensions: int) -> Path:
    root = Path(root).resolve()
    payload = build_index_manifest(root, embedding_model, dimensions)
    target = root / INDEX_MANIFEST_NAME
    temporary = root / f".{INDEX_MANIFEST_NAME}.{uuid4().hex}.tmp"
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    try:
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def inspect_index_manifest(settings) -> dict:
    """Return only safe status labels; never deserialize index content."""
    root = Path(settings.project_root).resolve()
    manifest_path = root / INDEX_MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != INDEX_MANIFEST_SCHEMA:
            raise ValueError("unsupported schema")
        embedding = manifest["embedding"]
        stores = manifest["stores"]
        if not isinstance(stores, dict):
            raise TypeError("stores must be an object")
        manifest_status = "ready"
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        manifest = {}
        embedding = {}
        stores = {}
        manifest_status = "missing" if not manifest_path.is_file() else "invalid"

    embedding_status = "ready" if (
        manifest_status == "ready"
        and embedding.get("model") == settings.embedding_model
        and embedding.get("dimensions") == settings.embedding_dimensions
    ) else ("mismatch" if manifest_status == "ready" else "unverified")

    index_statuses = {}
    for source in settings.enabled_retrieval_sources:
        directory = root / STORE_DIRECTORIES[source]
        file_specs = (stores.get(source) or {}).get("files", {})
        status = "ready"
        for name in INDEX_FILES:
            path = directory / name
            if not path.is_file() or path.stat().st_size <= 0:
                status = "missing"
                break
            spec = file_specs.get(name)
            if manifest_status != "ready" or not isinstance(spec, dict):
                status = "unverified"
                break
            if (
                spec.get("size_bytes") != path.stat().st_size
                or spec.get("sha256") != file_sha256(path)
            ):
                status = "integrity_mismatch"
                break
        index_statuses[source] = {"status": status}

    return {
        "manifest": {"status": manifest_status},
        "embedding_contract": {"status": embedding_status},
        "indexes": index_statuses,
    }
