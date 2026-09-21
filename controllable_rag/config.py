"""Typed application configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from .policy import RETRIEVAL_SOURCES, validate_evidence_minimum, validate_sources

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _positive_int(name, default):
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer, got {raw_value!r}") from error
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero, got {value}")
    return value


def _positive_float(name, default):
    raw_value = os.getenv(name, str(default))
    try:
        value = float(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be a number, got {raw_value!r}") from error
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero, got {value}")
    return value


def _boolean(name, default=False):
    raw_value = os.getenv(name, str(default)).strip().lower()
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean, got {raw_value!r}")


def _retrieval_sources(name="RAG_ENABLED_SOURCES", default=RETRIEVAL_SOURCES):
    raw_value = os.getenv(name, ",".join(default))
    values = tuple(part.strip().lower() for part in raw_value.split(",") if part.strip())
    return validate_sources(values, name)


@dataclass(frozen=True)
class Settings:
    """Runtime settings with validation and secret-safe representation."""

    project_root: Path = PROJECT_ROOT
    api_key: str | None = field(default=None, repr=False)
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    chat_model: str = "qwen3.8-max"
    embedding_model: str = "text-embedding-v4"
    embedding_dimensions: int = 1536
    max_retries: int = 5
    request_timeout_seconds: int = 60
    circuit_failure_threshold: int = 3
    circuit_recovery_seconds: float = 30.0
    chunks_top_k: int = 1
    summaries_top_k: int = 1
    quotes_top_k: int = 10
    enabled_retrieval_sources: tuple[str, ...] = RETRIEVAL_SOURCES
    min_evidence_records: int = 1
    agent_max_steps: int = 8
    grounding_max_attempts: int = 2
    agent_max_model_requests: int = 40
    agent_max_total_tokens: int = 20000
    agent_max_elapsed_seconds: float = 120.0
    agent_max_embedding_requests: int = 12
    agent_max_embedding_inputs: int = 20
    api_max_concurrent_requests: int = 8
    trace_enabled: bool = False
    trace_directory: Path | None = None

    def __post_init__(self):
        # Direct Settings injection must follow the same contract as .env parsing.
        if self.api_key is not None:
            if not isinstance(self.api_key, str):
                raise ValueError("api_key must be a string or None")
            object.__setattr__(self, "api_key", self.api_key.strip() or None)
        object.__setattr__(
            self, "enabled_retrieval_sources",
            validate_sources(self.enabled_retrieval_sources),
        )
        validate_evidence_minimum(self.min_evidence_records)
        if type(self.trace_enabled) is not bool:
            raise ValueError("trace_enabled must be a boolean")
        if (
            type(self.api_max_concurrent_requests) is not int
            or self.api_max_concurrent_requests <= 0
        ):
            raise ValueError("api_max_concurrent_requests must be a positive integer")
        if self.trace_directory is not None:
            object.__setattr__(self, "trace_directory", Path(self.trace_directory).resolve())

    @property
    def effective_trace_directory(self):
        return self.trace_directory or (self.project_root / "runtime_traces")

    @classmethod
    def from_env(cls, project_root=None):
        root = Path(project_root or PROJECT_ROOT).resolve()
        load_dotenv(root / ".env")
        trace_directory = Path(os.getenv("RAG_TRACE_DIR", "runtime_traces"))
        if not trace_directory.is_absolute():
            trace_directory = root / trace_directory
        return cls(
            project_root=root,
            api_key=(
                os.getenv("QWEN_API_KEY")
                or os.getenv("DASHSCOPE_API_KEY")
                or os.getenv("OPENAI_API_KEY")
            ),
            base_url=os.getenv(
                "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ).rstrip("/"),
            chat_model=os.getenv("QWEN_MODEL", "qwen3.8-max"),
            embedding_model=os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v4"),
            embedding_dimensions=_positive_int("QWEN_EMBEDDING_DIMENSIONS", 1536),
            max_retries=_positive_int("QWEN_MAX_RETRIES", 5),
            request_timeout_seconds=_positive_int("QWEN_TIMEOUT_SECONDS", 60),
            circuit_failure_threshold=_positive_int(
                "QWEN_CIRCUIT_FAILURE_THRESHOLD", 3
            ),
            circuit_recovery_seconds=_positive_float(
                "QWEN_CIRCUIT_RECOVERY_SECONDS", 30.0
            ),
            chunks_top_k=_positive_int("RAG_CHUNKS_TOP_K", 1),
            summaries_top_k=_positive_int("RAG_SUMMARIES_TOP_K", 1),
            quotes_top_k=_positive_int("RAG_QUOTES_TOP_K", 10),
            enabled_retrieval_sources=_retrieval_sources(),
            min_evidence_records=_positive_int("RAG_MIN_EVIDENCE_RECORDS", 1),
            agent_max_steps=_positive_int("AGENT_MAX_STEPS", 8),
            grounding_max_attempts=_positive_int("GROUNDING_MAX_ATTEMPTS", 2),
            agent_max_model_requests=_positive_int("AGENT_MAX_MODEL_REQUESTS", 40),
            agent_max_total_tokens=_positive_int("AGENT_MAX_TOTAL_TOKENS", 20000),
            agent_max_elapsed_seconds=_positive_float(
                "AGENT_MAX_ELAPSED_SECONDS", 120.0
            ),
            agent_max_embedding_requests=_positive_int(
                "AGENT_MAX_EMBEDDING_REQUESTS", 12
            ),
            agent_max_embedding_inputs=_positive_int(
                "AGENT_MAX_EMBEDDING_INPUTS", 20
            ),
            api_max_concurrent_requests=_positive_int(
                "RAG_API_MAX_CONCURRENT_REQUESTS", 8
            ),
            trace_enabled=_boolean("RAG_TRACE_ENABLED", False),
            trace_directory=trace_directory,
        )

    def require_api_key(self):
        if not self.api_key:
            raise RuntimeError(
                "Missing QWEN_API_KEY (DASHSCOPE_API_KEY and OPENAI_API_KEY are also accepted)."
            )
        return self.api_key


@lru_cache(maxsize=1)
def get_settings():
    """Return one validated settings object for the current process."""
    return Settings.from_env()
