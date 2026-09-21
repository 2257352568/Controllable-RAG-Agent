"""Provider-level circuit breaking without retrying business graph nodes."""

from functools import lru_cache
from threading import Lock
from time import monotonic

from langchain_core.embeddings import Embeddings
from langchain_core.runnables import RunnableLambda

TRANSIENT_EXCEPTION_NAMES = {
    "APIConnectionError", "APITimeoutError", "ConnectError", "ConnectTimeout",
    "ConnectionError", "NetworkError", "PoolTimeout", "ReadError", "ReadTimeout",
    "RateLimitError", "ServiceUnavailableError", "Timeout", "TimeoutError",
}
TRANSIENT_HTTP_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def is_transient_provider_error(error):
    """Classify only transport, throttling and server failures as breaker failures."""
    current = error
    visited = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if type(current).__name__ in TRANSIENT_EXCEPTION_NAMES:
            return True
        status = getattr(current, "status_code", None)
        if status is None:
            response = getattr(current, "response", None)
            status = getattr(response, "status_code", None)
        if status in TRANSIENT_HTTP_STATUS_CODES:
            return True
        current = current.__cause__ or current.__context__
    return False


class CircuitOpenError(RuntimeError):
    """Safe fast-failure raised without contacting the provider."""

    def __init__(self, state, retry_after_seconds):
        self.diagnostics = {
            "status": "rejected",
            "error_type": type(self).__name__,
            "circuit_state": state,
            "retry_after_seconds": round(max(0.0, retry_after_seconds), 3),
        }
        super().__init__("Model provider circuit is open")


class ProviderCircuitBreaker:
    """Thread-safe closed/open/half-open circuit for one provider deployment."""

    def __init__(self, failure_threshold, recovery_seconds, clock=monotonic):
        if int(failure_threshold) <= 0 or float(recovery_seconds) <= 0:
            raise ValueError("Circuit threshold and recovery_seconds must be positive")
        self.failure_threshold = int(failure_threshold)
        self.recovery_seconds = float(recovery_seconds)
        self._clock = clock
        self._lock = Lock()
        self._failures = 0
        self._opened_at = None
        self._half_open_trial = False

    def before_call(self):
        with self._lock:
            if self._opened_at is None:
                return
            elapsed = self._clock() - self._opened_at
            if elapsed < self.recovery_seconds:
                raise CircuitOpenError("open", self.recovery_seconds - elapsed)
            if self._half_open_trial:
                raise CircuitOpenError("half_open", 0.0)
            self._half_open_trial = True

    def record_success(self):
        with self._lock:
            self._failures = 0
            self._opened_at = None
            self._half_open_trial = False

    def record_transient_failure(self):
        with self._lock:
            self._failures += 1
            if self._half_open_trial or self._failures >= self.failure_threshold:
                self._opened_at = self._clock()
            self._half_open_trial = False

    def call(self, function, *args, **kwargs):
        self.before_call()
        try:
            result = function(*args, **kwargs)
        except Exception as error:
            if is_transient_provider_error(error):
                self.record_transient_failure()
            else:
                # A provider response or local contract error proves connectivity;
                # it must not poison a shared availability circuit.
                self.record_success()
            raise
        self.record_success()
        return result


class CircuitBreakerModel:
    """Preserve chat and embedding interfaces while sharing one breaker."""

    def __init__(self, target, breaker):
        self._target = target
        self._breaker = breaker

    def invoke(self, value, config=None, **kwargs):
        return self._breaker.call(
            self._target.invoke, value, config=config, **kwargs
        )

    def with_structured_output(self, schema, **kwargs):
        runnable = self._target.with_structured_output(schema, **kwargs)
        return RunnableLambda(
            lambda value, config=None: self._breaker.call(
                runnable.invoke, value, config=config
            )
        )

    def embed_query(self, text, **kwargs):
        return self._breaker.call(self._target.embed_query, text, **kwargs)

    def embed_documents(self, texts, **kwargs):
        return self._breaker.call(self._target.embed_documents, texts, **kwargs)

    def __getattr__(self, name):
        return getattr(self._target, name)


class CircuitBreakerEmbeddings(CircuitBreakerModel, Embeddings):
    """Preserve the nominal embedding interface required by vector stores.

    FAISS uses ``isinstance(..., Embeddings)`` to distinguish an embedding
    object from its deprecated callable path, so duck typing alone is not
    sufficient for this adapter.
    """


@lru_cache(maxsize=16)
def shared_circuit_breaker(key, failure_threshold, recovery_seconds):
    """Share availability state across clients for the same deployment/model kind."""
    del key  # Its value participates in the cache key without entering diagnostics.
    return ProviderCircuitBreaker(failure_threshold, recovery_seconds)
