"""Construction of the three local FAISS retrievers."""

import pickle
from functools import lru_cache
from pathlib import Path

from langchain_community.vectorstores import FAISS

from .config import RETRIEVAL_SOURCES, Settings, get_settings
from .models import create_embedding_model
from .policy import validate_sources

SOURCE_CONFIG = {
    "chunks": ("chunks_vector_store", "chunks_top_k"),
    "summaries": ("chapter_summaries_vector_store", "summaries_top_k"),
    "quotes": ("book_quotes_vectorstore", "quotes_top_k"),
}


def _load_trusted_store(directory, embeddings):
    """Read repository-controlled FAISS/docstore files, including Unicode paths.

    The pickle has the same trust requirements as FAISS.load_local(...,
    allow_dangerous_deserialization=True). Never pass uploaded/untrusted indexes.
    Python opens the file; the native library receives bytes rather than a Windows
    narrow-character filename that can corrupt non-ASCII directory names.
    """
    import faiss

    directory = Path(directory)
    with (directory / "index.faiss").open("rb") as stream:
        index = faiss.read_index(faiss.PyCallbackIOReader(stream.read))
    with (directory / "index.pkl").open("rb") as stream:
        docstore, index_to_docstore_id = pickle.load(stream)
    return FAISS(embeddings, index, docstore, index_to_docstore_id)


def _create_retriever(source, settings, embeddings):
    validate_sources([source])
    directory, top_k_field = SOURCE_CONFIG[source]
    store = _load_trusted_store(
        settings.project_root / directory,
        embeddings,
    )
    return store.as_retriever(search_kwargs={"k": getattr(settings, top_k_field)})


def create_retriever(source, settings: Settings | None = None):
    settings = settings or get_settings()
    return _create_retriever(source, settings, create_embedding_model(settings))


@lru_cache(maxsize=3)
def get_retriever(source):
    """Load only the requested trusted local index; callers enforce their allowlist."""
    return create_retriever(source)


def create_retrievers(settings: Settings | None = None):
    """Legacy tuple API for notebooks explicitly requesting all three sources."""
    settings = settings or get_settings()
    embeddings = create_embedding_model(settings)
    return tuple(
        _create_retriever(source, settings, embeddings)
        for source in RETRIEVAL_SOURCES
    )


@lru_cache(maxsize=1)
def get_retrievers():
    """Load local indexes only when retrieval is first requested."""
    return create_retrievers()
