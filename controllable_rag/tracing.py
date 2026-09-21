"""Privacy-minimized, checksum-verifiable persistence for completed Agent traces."""

import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

TRACE_SCHEMA_VERSION = "2026-09-14.1"
SUPPORTED_TRACE_SCHEMA_VERSIONS = {
    "2026-09-12.1", "2026-09-13.1", TRACE_SCHEMA_VERSION,
}
EVENT_FIELDS = {
    "sequence", "node", "duration_ms", "status", "step_count", "tool",
    "model_requests", "input_tokens", "output_tokens", "total_tokens",
    "token_accounting_available", "budget_enforcement",
}
POLICY_EVENT_FIELDS = {"source", "action", "enabled_sources", "step_count"}
BUDGET_FIELDS = {
    "reason", "max_model_requests", "max_total_tokens",
    "model_requests_started", "tokens_committed", "tokens_reserved",
    "budget_accounting_complete", "requested_token_reservation",
    "max_embedding_requests", "max_embedding_inputs", "embedding_requests",
    "embedding_inputs", "requested_embedding_inputs", "max_elapsed_seconds",
    "elapsed_seconds", "remaining_seconds",
}
ERROR_FIELDS = {
    "node", "duration_ms", "status", "error_type",
    "circuit_state", "retry_after_seconds", "thread_id_present",
}


def new_trace_id():
    return str(uuid4())


def validate_trace_id(value):
    try:
        parsed = UUID(str(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError("trace_id must be a valid UUID") from error
    return str(parsed)


def _project_fields(items, allowed):
    return [
        {key: item[key] for key in allowed if key in item}
        for item in (items or []) if isinstance(item, dict)
    ]


def build_trace_payload(state):
    """Create an allowlisted record that excludes prompts and generated content."""
    trace_id = validate_trace_id(state["trace_id"])
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "trace_id": trace_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "termination_reason": state.get("termination_reason", "unknown"),
        "usage": {
            "model_requests": int(state.get("model_requests") or 0),
            "input_tokens": int(state.get("input_tokens") or 0),
            "output_tokens": int(state.get("output_tokens") or 0),
            "total_tokens": int(state.get("total_tokens") or 0),
            "token_accounting_available": bool(
                state.get("token_accounting_available", False)
            ),
        },
        "control": {
            "step_count": int(state.get("step_count") or 0),
            "retrieval_count": int(state.get("retrieval_count") or 0),
            "answer_attempts": int(state.get("answer_attempts") or 0),
            "max_steps": state.get("max_steps"),
            "max_model_requests": state.get("max_model_requests"),
            "max_total_tokens": state.get("max_total_tokens"),
            "max_embedding_requests": state.get("max_embedding_requests"),
            "max_embedding_inputs": state.get("max_embedding_inputs"),
            "embedding_requests": int(state.get("embedding_requests") or 0),
            "embedding_inputs": int(state.get("embedding_inputs") or 0),
            "enabled_retrieval_sources": list(
                state.get("enabled_retrieval_sources") or []
            ),
            "min_evidence_records": state.get("min_evidence_records"),
            "evidence_count": len({
                record.get("id") for record in (state.get("evidence_records") or [])
                if isinstance(record, dict) and record.get("id")
            }),
            "citation_count": len(state.get("citations") or []),
            "claim_citation_count": len(state.get("claim_citations") or []),
            "budget_mode": state.get("budget_mode", "unknown"),
            "evidence_gate_reason": state.get("evidence_gate_reason", ""),
        },
        "events": _project_fields(state.get("trace_events"), EVENT_FIELDS),
        "source_policy_events": _project_fields(
            state.get("source_policy_events"), POLICY_EVENT_FIELDS
        ),
        "budget_diagnostics": {
            key: state["budget_diagnostics"][key]
            for key in BUDGET_FIELDS
            if key in (state.get("budget_diagnostics") or {})
        },
        "error_diagnostics": {
            key: state["error_diagnostics"][key]
            for key in ERROR_FIELDS
            if key in (state.get("error_diagnostics") or {})
        },
    }


def _canonical_bytes(payload):
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def trace_envelope(state):
    payload = build_trace_payload(state)
    return {
        "payload": payload,
        "payload_sha256": sha256(_canonical_bytes(payload)).hexdigest(),
    }


def persist_trace(state, directory):
    """Atomically write one immutable-by-name trace file and return its path."""
    envelope = trace_envelope(state)
    trace_id = envelope["payload"]["trace_id"]
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{trace_id}.json"
    temporary = directory / f".{trace_id}.{uuid4().hex}.tmp"
    temporary.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    try:
        # Hard-linking a complete temporary file is atomic and fails if the UUID
        # already exists, so a caller cannot silently rewrite trace history.
        os.link(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def verify_trace(path):
    try:
        envelope = json.loads(Path(path).read_text(encoding="utf-8"))
        payload = envelope["payload"]
        expected = envelope["payload_sha256"]
        validate_trace_id(payload["trace_id"])
        if payload.get("schema_version") not in SUPPORTED_TRACE_SCHEMA_VERSIONS:
            return False, "unsupported schema version"
        if sha256(_canonical_bytes(payload)).hexdigest() != expected:
            return False, "payload hash mismatch"
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return False, f"invalid trace: {type(error).__name__}"
    return True, "ok"
