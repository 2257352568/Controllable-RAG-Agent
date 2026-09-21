"""Deterministic retrieval controls shared by configuration and runtime entrypoints."""

RETRIEVAL_SOURCES = ("chunks", "summaries", "quotes")
POLICY_VERSION = "2026-09-12.2"


def validate_sources(values, name="enabled_retrieval_sources"):
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError(f"{name} must contain at least one source in a list or tuple")
    if any(not isinstance(value, str) or value not in RETRIEVAL_SOURCES for value in values):
        raise ValueError(f"{name} contains unsupported sources; choose from {RETRIEVAL_SOURCES}")
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(values)


def validate_evidence_minimum(value):
    # bool and fractional numbers must not silently become valid integer limits.
    if type(value) is not int or value <= 0:
        raise ValueError("min_evidence_records must be an integer greater than zero")
    return value


def unique_evidence_count(records):
    """Count identities in internally validated evidence, not rows or independent facts.

    This function does not establish provenance for arbitrary caller-supplied records.
    The retrieval/grounding pipeline establishes that provenance before storing them.
    """
    return len({
        record["id"] for record in (records or [])
        if isinstance(record, dict)
        and isinstance(record.get("id"), str)
        and record["id"].strip()
    })
