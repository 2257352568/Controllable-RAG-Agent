"""FastAPI delivery layer with a privacy-minimized SSE event contract."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from threading import BoundedSemaphore, Lock
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.background import BackgroundTask

from .config import Settings, get_settings
from .graph import create_agent
from .index_manifest import inspect_index_manifest
from .runtime import ConcurrentThreadExecutionError


class QueryRequest(BaseModel):
    """Public query controls; unknown fields fail closed."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)
    max_steps: int | None = Field(default=None, ge=1, le=50)
    max_model_requests: int | None = Field(default=None, ge=1, le=200)
    max_total_tokens: int | None = Field(default=None, ge=100, le=500_000)
    max_elapsed_seconds: float | None = Field(default=None, gt=0, le=3600)
    max_embedding_requests: int | None = Field(default=None, ge=1, le=100)
    max_embedding_inputs: int | None = Field(default=None, ge=1, le=500)
    enabled_retrieval_sources: (
        list[Literal["chunks", "summaries", "quotes"]] | None
    ) = Field(default=None, min_length=1)
    min_evidence_records: int | None = Field(default=None, ge=1, le=20)
    trace_enabled: bool | None = None

    @field_validator("question")
    @classmethod
    def reject_blank_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must not be blank")
        return value

    @field_validator("enabled_retrieval_sources")
    @classmethod
    def reject_duplicate_sources(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if len(value) != len(set(value)):
            raise ValueError("enabled_retrieval_sources must not contain duplicates")
        return value

    def agent_inputs(self) -> dict[str, Any]:
        # Omitted controls must be resolved by the single Settings source of truth.
        return self.model_dump(exclude_none=True)


def _safe_citations(state: dict[str, Any]) -> list[dict[str, Any]]:
    citations = []
    for citation in state.get("citations") or []:
        metadata = citation.get("metadata") or {}
        page_candidates = metadata.get("location_candidates")
        if not (
            metadata.get("page") is None
            and metadata.get("chapter") is None
            and isinstance(page_candidates, list)
            and len(page_candidates) >= 2
            and all(
                isinstance(page, int) and not isinstance(page, bool) and page >= 0
                for page in page_candidates
            )
        ):
            page_candidates = None
        projected = {
            "id": citation.get("id"),
            "source": citation.get("source"),
            "rank": citation.get("rank"),
            "page": metadata.get("page"),
            "chapter": metadata.get("chapter"),
        }
        if page_candidates:
            projected["page_candidates"] = list(dict.fromkeys(page_candidates))
        citations.append(projected)
    return citations


def _safe_claim_citations(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose only validated IDs and claim text already present in the response."""
    allowed_ids = {
        citation.get("id")
        for citation in state.get("citations") or []
        if isinstance(citation, dict) and citation.get("id")
    }
    response = str(state.get("response", ""))
    projected = []
    for item in state.get("claim_citations") or []:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim", "")).strip()
        supporting_ids = []
        for evidence_id in item.get("supporting_ids") or []:
            if evidence_id in allowed_ids and evidence_id not in supporting_ids:
                supporting_ids.append(evidence_id)
        if claim and claim in response and supporting_ids:
            projected.append({"claim": claim, "supporting_ids": supporting_ids})
    return projected


def _safe_progress(node: str, state: dict[str, Any]) -> dict[str, Any]:
    """Never expose prompts, retrieved text, plans, or internal explanations."""
    return {
        "node": node,
        "curr_state": state.get("curr_state", node),
        "step_count": state.get("step_count", 0),
        "retrieval_count": state.get("retrieval_count", 0),
        "model_requests": state.get("model_requests", 0),
        "total_tokens": state.get("total_tokens", 0),
        "embedding_requests": state.get("embedding_requests", 0),
        "elapsed_seconds": state.get("elapsed_seconds", 0.0),
    }


def _safe_result(state: dict[str, Any], request_id: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "response": state.get("response", ""),
        "termination_reason": state.get("termination_reason", "unknown"),
        "citations": _safe_citations(state),
        "claim_citations": _safe_claim_citations(state),
        "usage": {
            "step_count": state.get("step_count", 0),
            "retrieval_count": state.get("retrieval_count", 0),
            "model_requests": state.get("model_requests", 0),
            "input_tokens": state.get("input_tokens", 0),
            "output_tokens": state.get("output_tokens", 0),
            "total_tokens": state.get("total_tokens", 0),
            "embedding_requests": state.get("embedding_requests", 0),
            "embedding_inputs": state.get("embedding_inputs", 0),
            "elapsed_seconds": state.get("elapsed_seconds", 0.0),
            "token_accounting_available": state.get(
                "token_accounting_available", False
            ),
        },
        "trace_id": request_id,
    }


def _sse(event: str, data: dict[str, Any], sequence: int) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"id: {sequence}\nevent: {event}\ndata: {payload}\n\n"


def readiness_report(settings: Settings) -> dict[str, Any]:
    """Check local prerequisites without network calls or pickle deserialization."""
    index_components = inspect_index_manifest(settings)
    api_key_ready = bool(settings.api_key)
    ready = api_key_ready and all(
        component["status"] == "ready"
        for component in (
            index_components["manifest"],
            index_components["embedding_contract"],
            *index_components["indexes"].values(),
        )
    )
    return {
        "status": "ready" if ready else "not_ready",
        "components": {
            "api_key": {"status": "ready" if api_key_ready else "missing"},
            **index_components,
        },
        "scope": "local_prerequisites_only",
    }


def create_api(
    agent_factory: Callable[[], Any] = create_agent,
    max_concurrent_requests: int | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Create an app; Agent construction stays lazy and replaceable in tests."""
    app = FastAPI(
        title="Controllable Agentic RAG API",
        version="1.0.0",
        description="Bounded Qwen-backed RAG queries with optional SSE progress.",
    )
    app.state.agent_factory = agent_factory
    app.state.agent = None
    app.state.agent_lock = Lock()
    resolved_settings = settings or get_settings()
    app.state.settings = resolved_settings
    capacity = (
        resolved_settings.api_max_concurrent_requests
        if max_concurrent_requests is None
        else int(max_concurrent_requests)
    )
    if capacity <= 0:
        raise ValueError("max_concurrent_requests must be greater than zero")
    app.state.max_concurrent_requests = capacity
    app.state.request_slots = BoundedSemaphore(capacity)

    def get_agent(request: Request):
        agent = request.app.state.agent
        if agent is not None:
            return agent
        with request.app.state.agent_lock:
            if request.app.state.agent is None:
                request.app.state.agent = request.app.state.agent_factory()
            return request.app.state.agent

    def overload_response(request_id: str) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"request_id": request_id, "error": "server_overloaded"},
            headers={"Retry-After": "1", "X-Request-ID": request_id},
        )

    def agent_inputs(payload: QueryRequest, request_id: str) -> dict[str, Any]:
        inputs = payload.agent_inputs()
        # Generated after validation: clients cannot choose or overwrite trace IDs.
        inputs["trace_id"] = request_id
        return inputs

    def execution_error(request_id: str, error: str, status_code: int) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={
                "request_id": request_id,
                "trace_id": request_id,
                "error": error,
            },
            headers={"X-Request-ID": request_id},
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        # Liveness must not initialize paid models or deserialize local indexes.
        return {"status": "ok"}

    @app.get("/ready")
    def ready(request: Request) -> JSONResponse:
        report = readiness_report(request.app.state.settings)
        return JSONResponse(
            status_code=200 if report["status"] == "ready" else 503,
            content=report,
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/v1/query")
    def query(payload: QueryRequest, request: Request):
        request_id = str(uuid4())
        if not request.app.state.request_slots.acquire(blocking=False):
            return overload_response(request_id)
        try:
            state = get_agent(request).invoke(agent_inputs(payload, request_id))
        except ConcurrentThreadExecutionError:
            return execution_error(request_id, "request_conflict", 409)
        except Exception:
            return execution_error(request_id, "agent_execution_failed", 500)
        finally:
            request.app.state.request_slots.release()
        return JSONResponse(
            content=_safe_result(state, request_id),
            headers={"X-Request-ID": request_id},
        )

    @app.post("/v1/query/stream")
    def query_stream(payload: QueryRequest, request: Request) -> StreamingResponse:
        request_id = str(uuid4())
        if not request.app.state.request_slots.acquire(blocking=False):
            return overload_response(request_id)

        def events() -> Iterator[str]:
            sequence = 1
            last_state: dict[str, Any] = {}
            yield _sse(
                "started",
                {"request_id": request_id, "trace_id": request_id},
                sequence,
            )
            try:
                agent = get_agent(request)
                for chunk in agent.stream(agent_inputs(payload, request_id)):
                    node, last_state = next(iter(chunk.items()))
                    sequence += 1
                    yield _sse(
                        "progress", _safe_progress(node, last_state), sequence
                    )
                sequence += 1
                yield _sse(
                    "completed", _safe_result(last_state, request_id), sequence
                )
            except ConcurrentThreadExecutionError:
                sequence += 1
                yield _sse(
                    "error",
                    {
                        "request_id": request_id,
                        "trace_id": request_id,
                        "error": "request_conflict",
                    },
                    sequence,
                )
            except Exception:
                sequence += 1
                yield _sse(
                    "error",
                    {
                        "request_id": request_id,
                        "trace_id": request_id,
                        "error": "agent_execution_failed",
                    },
                    sequence,
                )
        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            background=BackgroundTask(request.app.state.request_slots.release),
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "X-Request-ID": request_id,
            },
        )

    return app


app = create_api()
