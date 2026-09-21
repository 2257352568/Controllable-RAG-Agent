"""Per-request chat budget enforced by the shared model factory."""

import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock
from time import monotonic

from langchain_core.runnables import RunnableLambda


class ModelBudgetExceeded(RuntimeError):
    """A safe control-flow exception raised before a provider request is sent."""

    def __init__(self, reason, diagnostics):
        self.reason = reason
        self.diagnostics = {"reason": reason, **diagnostics}
        super().__init__(reason)


@dataclass(frozen=True)
class Reservation:
    tokens: int


class BudgetLedger:
    """Thread-safe request counter and conservative token reservation ledger."""

    def __init__(
        self,
        max_requests,
        max_tokens,
        initial_requests=0,
        initial_tokens=0,
        accounting_complete=True,
        max_elapsed_seconds=None,
        initial_elapsed_seconds=0.0,
        max_embedding_requests=None,
        max_embedding_inputs=None,
        initial_embedding_requests=0,
        initial_embedding_inputs=0,
        clock=monotonic,
    ):
        self.max_requests = int(max_requests)
        self.max_tokens = int(max_tokens)
        self.requests_started = int(initial_requests)
        self.tokens_committed = int(initial_tokens)
        self.tokens_reserved = 0
        self.max_embedding_requests = (
            int(max_embedding_requests) if max_embedding_requests is not None else None
        )
        self.max_embedding_inputs = (
            int(max_embedding_inputs) if max_embedding_inputs is not None else None
        )
        self.embedding_requests = int(initial_embedding_requests)
        self.embedding_inputs = int(initial_embedding_inputs)
        self.accounting_complete = bool(accounting_complete)
        self.max_elapsed_seconds = (
            float(max_elapsed_seconds) if max_elapsed_seconds is not None else None
        )
        self.initial_elapsed_seconds = float(initial_elapsed_seconds)
        self._clock = clock
        self._started_at = clock()
        self._lock = Lock()

    @property
    def elapsed_seconds(self):
        return self.initial_elapsed_seconds + max(0.0, self._clock() - self._started_at)

    def deadline_exhausted(self):
        return (
            self.max_elapsed_seconds is not None
            and self.elapsed_seconds >= self.max_elapsed_seconds
        )

    def reserve(self, token_upper_bound):
        token_upper_bound = max(1, int(token_upper_bound))
        with self._lock:
            diagnostics = self.snapshot()
            diagnostics["requested_token_reservation"] = token_upper_bound
            if self.deadline_exhausted():
                raise ModelBudgetExceeded("execution_deadline_exhausted", diagnostics)
            if self.requests_started >= self.max_requests:
                raise ModelBudgetExceeded(
                    "model_request_budget_exhausted", diagnostics
                )
            if (
                self.tokens_committed
                + self.tokens_reserved
                + token_upper_bound
                > self.max_tokens
            ):
                raise ModelBudgetExceeded("token_budget_exhausted", diagnostics)
            self.requests_started += 1
            self.tokens_reserved += token_upper_bound
        return Reservation(token_upper_bound)

    def settle(self, reservation, actual_tokens=None):
        with self._lock:
            self.tokens_reserved -= reservation.tokens
            if actual_tokens is None or actual_tokens <= 0:
                self.tokens_committed += reservation.tokens
                self.accounting_complete = False
            else:
                self.tokens_committed += int(actual_tokens)
                if actual_tokens > reservation.tokens:
                    # This signals a provider/tokenizer contract violation. The
                    # request cannot be undone, but the overshoot remains visible.
                    self.accounting_complete = False

    def reserve_embedding(self, input_count):
        input_count = int(input_count)
        if input_count <= 0:
            raise ValueError("embedding input_count must be greater than zero")
        with self._lock:
            diagnostics = self.snapshot()
            diagnostics["requested_embedding_inputs"] = input_count
            if self.deadline_exhausted():
                raise ModelBudgetExceeded("execution_deadline_exhausted", diagnostics)
            if (
                self.max_embedding_requests is not None
                and self.embedding_requests >= self.max_embedding_requests
            ):
                raise ModelBudgetExceeded(
                    "embedding_request_budget_exhausted", diagnostics
                )
            if (
                self.max_embedding_inputs is not None
                and self.embedding_inputs + input_count > self.max_embedding_inputs
            ):
                raise ModelBudgetExceeded("embedding_input_budget_exhausted", diagnostics)
            self.embedding_requests += 1
            self.embedding_inputs += input_count

    def snapshot(self):
        # Caller may already hold the lock; only read primitive fields here.
        snapshot = {
            "max_model_requests": self.max_requests,
            "max_total_tokens": self.max_tokens,
            "model_requests_started": self.requests_started,
            "tokens_committed": self.tokens_committed,
            "tokens_reserved": self.tokens_reserved,
            "budget_accounting_complete": self.accounting_complete,
        }
        if self.max_elapsed_seconds is not None:
            snapshot.update(
                max_elapsed_seconds=self.max_elapsed_seconds,
                elapsed_seconds=round(self.elapsed_seconds, 6),
                remaining_seconds=round(
                    max(0.0, self.max_elapsed_seconds - self.elapsed_seconds), 6
                ),
            )
        if self.max_embedding_requests is not None:
            snapshot.update(
                max_embedding_requests=self.max_embedding_requests,
                embedding_requests=self.embedding_requests,
            )
        if self.max_embedding_inputs is not None:
            snapshot.update(
                max_embedding_inputs=self.max_embedding_inputs,
                embedding_inputs=self.embedding_inputs,
            )
        return snapshot


_ACTIVE_LEDGER = ContextVar("controllable_rag_budget_ledger", default=None)


def active_budget_state():
    """Return checkpoint-safe cumulative budget fields for the active execution."""
    ledger = _ACTIVE_LEDGER.get()
    if ledger is None:
        return {}
    diagnostics = ledger.snapshot()
    return {
        "model_requests": diagnostics["model_requests_started"],
        "total_tokens": diagnostics["tokens_committed"],
        "token_accounting_available": diagnostics["budget_accounting_complete"],
        "budget_mode": "hard_preflight_with_boundary_fallback",
        "budget_diagnostics": diagnostics,
        "elapsed_seconds": diagnostics.get("elapsed_seconds", 0.0),
        "embedding_requests": diagnostics.get("embedding_requests", 0),
        "embedding_inputs": diagnostics.get("embedding_inputs", 0),
    }


class BudgetedEmbeddingModel:
    """Count embedding operations and inputs before dispatch when a ledger is active."""

    def __init__(self, model):
        self._model = model

    @staticmethod
    def _reserve(input_count):
        ledger = _ACTIVE_LEDGER.get()
        if ledger is not None:
            ledger.reserve_embedding(input_count)

    def embed_query(self, text, **kwargs):
        self._reserve(1)
        return self._model.embed_query(text, **kwargs)

    def embed_documents(self, texts, **kwargs):
        texts = list(texts)
        self._reserve(len(texts))
        return self._model.embed_documents(texts, **kwargs)

    def __getattr__(self, name):
        return getattr(self._model, name)


@contextmanager
def activate_budget(ledger):
    token = _ACTIVE_LEDGER.set(ledger)
    try:
        yield ledger
    finally:
        _ACTIVE_LEDGER.reset(token)


def _byte_upper_bound(value):
    if hasattr(value, "to_string"):
        value = value.to_string()
    return len(str(value).encode("utf-8", errors="replace"))


def _schema_bytes(schema):
    try:
        payload = schema.schema()
    except (AttributeError, TypeError):
        payload = str(schema)
    return len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))


def _actual_tokens(result):
    raw = result.get("raw") if isinstance(result, dict) else result
    usage = getattr(raw, "usage_metadata", None) or {}
    if usage.get("total_tokens") is not None:
        return int(usage["total_tokens"])
    metadata = getattr(raw, "response_metadata", None) or {}
    token_usage = metadata.get("token_usage") or metadata.get("usage") or {}
    total = token_usage.get("total_tokens") or token_usage.get("total_tokens_count")
    return int(total) if total is not None else None


def _invoke_with_budget(
    runnable, value, max_output_tokens, schema_size=0, config=None,
    unwrap_structured=False, **kwargs
):
    ledger = _ACTIVE_LEDGER.get()
    if ledger is None:
        result = runnable.invoke(value, config=config, **kwargs)
        if unwrap_structured:
            if result.get("parsing_error") is not None:
                raise result["parsing_error"]
            return result["parsed"]
        return result

    # UTF-8 bytes upper-bound normal text token count; schema bytes and fixed
    # protocol headroom cover structured-output/tool framing not visible in input.
    reservation = ledger.reserve(
        _byte_upper_bound(value) + schema_size + int(max_output_tokens) + 512
    )
    try:
        result = runnable.invoke(value, config=config, **kwargs)
        actual = _actual_tokens(result)
    except Exception:
        # A provider attempt still consumes the request slot. Without a response,
        # retain the conservative token reservation as committed usage.
        ledger.settle(reservation, None)
        raise
    ledger.settle(reservation, actual)
    if unwrap_structured:
        if result.get("parsing_error") is not None:
            raise result["parsing_error"]
        return result["parsed"]
    return result


class BudgetedChatModel:
    """Small adapter preserving the interfaces used by this project."""

    def __init__(self, model, max_output_tokens):
        self._model = model
        self._max_output_tokens = int(max_output_tokens)

    def invoke(self, value, config=None, **kwargs):
        return _invoke_with_budget(
            self._model, value, self._max_output_tokens, config=config, **kwargs
        )

    def with_structured_output(self, schema, **kwargs):
        # Raw response metadata is retained internally for exact settlement, while
        # callers continue receiving the parsed Pydantic object.
        kwargs.pop("include_raw", None)
        runnable = self._model.with_structured_output(
            schema, include_raw=True, **kwargs
        )
        schema_size = _schema_bytes(schema)

        def invoke(value, config=None):
            return _invoke_with_budget(
                runnable,
                value,
                self._max_output_tokens,
                schema_size=schema_size,
                config=config,
                unwrap_structured=True,
            )

        return RunnableLambda(invoke)

    def __getattr__(self, name):
        return getattr(self._model, name)
