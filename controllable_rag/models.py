"""Factories for chat and embedding models."""

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from .budget import BudgetedChatModel, BudgetedEmbeddingModel
from .config import Settings, get_settings
from .resilience import (
    CircuitBreakerEmbeddings,
    CircuitBreakerModel,
    shared_circuit_breaker,
)


def _with_circuit_breaker(model, settings, kind):
    breaker = shared_circuit_breaker(
        (settings.base_url, settings.chat_model if kind == "chat" else settings.embedding_model, kind),
        settings.circuit_failure_threshold,
        settings.circuit_recovery_seconds,
    )
    return CircuitBreakerModel(model, breaker)


def create_chat_model(max_tokens=2000, settings: Settings | None = None):
    """Create a Qwen chat client through Model Studio's compatible API."""
    settings = settings or get_settings()
    provider_options = {"extra_body": {"enable_thinking": False}}
    # langchain-openai 0.1.x only forwards provider extensions through
    # model_kwargs; 1.x exposes extra_body directly and warns on the old form.
    if "extra_body" in getattr(ChatOpenAI, "model_fields", {}):
        compatibility_kwargs = {"extra_body": provider_options["extra_body"]}
    else:
        compatibility_kwargs = {"model_kwargs": provider_options}
    model = ChatOpenAI(
        api_key=settings.require_api_key(),
        base_url=settings.base_url,
        model=settings.chat_model,
        temperature=0,
        max_tokens=max_tokens,
        max_retries=settings.max_retries,
        timeout=settings.request_timeout_seconds,
        **compatibility_kwargs,
    )
    # Circuit rejection happens outside the budget adapter, so it consumes no
    # logical request slot or conservative token reservation.
    return _with_circuit_breaker(
        BudgetedChatModel(model, max_tokens), settings, "chat"
    )


def create_embedding_model(settings: Settings | None = None):
    """Create the embedding client used by the local FAISS indexes."""
    settings = settings or get_settings()
    model = OpenAIEmbeddings(
        api_key=settings.require_api_key(),
        base_url=settings.base_url,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        chunk_size=10,
        max_retries=settings.max_retries,
        timeout=settings.request_timeout_seconds,
        check_embedding_ctx_length=False,
    )
    breaker = shared_circuit_breaker(
        (settings.base_url, settings.embedding_model, "embedding"),
        settings.circuit_failure_threshold,
        settings.circuit_recovery_seconds,
    )
    return CircuitBreakerEmbeddings(BudgetedEmbeddingModel(model), breaker)
