"""Rebuild the bundled FAISS stores with the configured Qwen embedding model."""

import shutil
from datetime import datetime

from langchain_community.vectorstores import FAISS

from controllable_rag.config import get_settings
from controllable_rag.index_manifest import write_index_manifest
from controllable_rag.models import create_embedding_model

PROJECT_ROOT = get_settings().project_root


STORE_NAMES = (
    "chunks_vector_store",
    "chapter_summaries_vector_store",
    "book_quotes_vectorstore",
)


def documents_in_index_order(store):
    return [
        store.docstore.search(store.index_to_docstore_id[position])
        for position in range(len(store.index_to_docstore_id))
    ]


def main():
    settings = get_settings()
    embeddings = create_embedding_model(settings=settings)
    backup_root = PROJECT_ROOT / "vector_store_backups" / datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root.mkdir(parents=True)

    for name in STORE_NAMES:
        store_path = PROJECT_ROOT / name
        old_store = FAISS.load_local(
            str(store_path), embeddings, allow_dangerous_deserialization=True
        )
        documents = documents_in_index_order(old_store)

        shutil.copytree(store_path, backup_root / name)
        new_store = FAISS.from_documents(documents, embeddings)
        new_store.save_local(str(store_path))
        print(f"Rebuilt {name}: {len(documents)} documents")

    manifest_path = write_index_manifest(
        PROJECT_ROOT, settings.embedding_model, settings.embedding_dimensions
    )
    print(f"Wrote verified index manifest: {manifest_path}")
    print(f"Original indexes backed up to: {backup_root}")


if __name__ == "__main__":
    main()
