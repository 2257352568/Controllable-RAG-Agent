"""Deterministic evidence identifiers and citation rendering."""

import re
from hashlib import sha256
from html import escape

CITATION_PATTERN = re.compile(r"\[([a-z]+-(?:p|ch|doc)[a-z0-9-]+)\]", re.IGNORECASE)
CLAIM_SPLIT_PATTERN = re.compile(r"(?<=[。！？])|(?<=[.!?])\s+|[\r\n]+")


def candidate_pages(metadata):
    values = metadata.get("location_candidates")
    if not isinstance(values, list):
        return []
    pages = []
    for value in values:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            if value not in pages:
                pages.append(value)
    return pages


def _location(source, metadata):
    if metadata.get("page") is not None:
        return f"p{metadata['page']}"
    if metadata.get("chapter") is not None:
        return f"ch{metadata['chapter']}"
    return "doc"


def make_evidence_record(source, rank, document):
    content = str(document.page_content)
    metadata = dict(document.metadata or {})
    digest = sha256(content.encode("utf-8", errors="replace")).hexdigest()[:10]
    return {
        "id": f"{source}-{_location(source, metadata)}-{digest}",
        "source": source,
        "rank": int(rank),
        "content": content,
        "metadata": metadata,
    }


def build_evidence_records(source, documents):
    return [
        make_evidence_record(source, rank, document)
        for rank, document in enumerate(documents, start=1)
    ]


def render_evidence(records):
    blocks = []
    for record in records:
        metadata = record.get("metadata", {})
        candidates = candidate_pages(metadata)
        location = (
            f"page={metadata['page']}"
            if metadata.get("page") is not None
            else f"chapter={metadata['chapter']}"
            if metadata.get("chapter") is not None
            else f"pages={'|'.join(map(str, candidates))};ambiguous"
            if candidates
            else "location=unavailable"
        )
        blocks.append(
            f'<evidence id="{record["id"]}" source="{record["source"]}" '
            f'location="{location}" trust="untrusted-retrieved-data">\n'
            f"[{record['id']}]\n{escape(str(record['content']), quote=False)}\n"
            "</evidence>"
        )
    return "\n\n".join(blocks)


def validate_citation_ids(candidate_ids, records):
    allowed = {record["id"] for record in records}
    valid = []
    for candidate in candidate_ids or []:
        cleaned = str(candidate).strip().strip("[]")
        if cleaned in allowed and cleaned not in valid:
            valid.append(cleaned)
    return valid


def _claim_key(text):
    text = re.sub(r"^\s*(?:[-*]\s*)?(?:answer\s*:\s*)?", "", str(text), flags=re.I)
    return " ".join(re.findall(r"\w+", text.casefold(), flags=re.UNICODE))


def answer_claim_keys(answer):
    """Return normalized non-empty answer sentences for coverage validation."""
    return [
        key
        for part in CLAIM_SPLIT_PATTERN.split(str(answer))
        if (key := _claim_key(part))
    ]


def validate_claim_citations(answer, candidates, records):
    """Validate a complete sentence-to-evidence map or fail the whole map closed."""
    answer_keys = answer_claim_keys(answer)
    if not answer_keys:
        return [], "answer_has_no_claims"
    if len(answer_keys) != len(set(answer_keys)):
        return [], "duplicate_answer_sentence"
    allowed = {record["id"] for record in records}
    validated = []
    seen_claims = set()
    for candidate in candidates or []:
        if hasattr(candidate, "model_dump"):
            candidate = candidate.model_dump()
        elif not isinstance(candidate, dict):
            candidate = {
                "claim": getattr(candidate, "claim", ""),
                "supporting_ids": getattr(candidate, "supporting_ids", []),
            }
        claim = str(candidate.get("claim", "")).strip()
        claim_key = _claim_key(claim)
        raw_ids = candidate.get("supporting_ids")
        if not isinstance(raw_ids, list):
            return [], "claim_supporting_ids_invalid"
        cleaned_ids = []
        for raw_id in raw_ids:
            cleaned = str(raw_id).strip().strip("[]")
            if cleaned not in allowed:
                return [], "claim_contains_unknown_evidence_id"
            if cleaned not in cleaned_ids:
                cleaned_ids.append(cleaned)
        if not claim_key or claim_key not in answer_keys:
            return [], "claim_not_found_as_answer_sentence"
        if claim_key in seen_claims:
            return [], "duplicate_claim_mapping"
        if not cleaned_ids:
            return [], "claim_has_no_evidence"
        seen_claims.add(claim_key)
        validated.append({"claim": claim, "supporting_ids": cleaned_ids})
    if seen_claims != set(answer_keys):
        return [], "not_every_answer_sentence_is_mapped"
    if [_claim_key(item["claim"]) for item in validated] != answer_keys:
        return [], "claim_order_mismatch"
    return validated, ""


def claim_citation_ids(claim_citations):
    """Return deterministic first-seen evidence IDs from validated claim mappings."""
    result = []
    for item in claim_citations or []:
        for evidence_id in item.get("supporting_ids", []):
            if evidence_id not in result:
                result.append(evidence_id)
    return result


def cited_records(candidate_ids, records):
    valid_ids = set(validate_citation_ids(candidate_ids, records))
    return [record for record in records if record["id"] in valid_ids]


def merge_evidence(existing, additions):
    merged = []
    seen = set()
    for record in [*(existing or []), *(additions or [])]:
        if record["id"] not in seen:
            seen.add(record["id"])
            merged.append(record)
    return merged


def render_distilled_context(text, supporting_ids):
    labels = " ".join(f"[{citation_id}]" for citation_id in supporting_ids)
    return (
        '<distilled-evidence trust="untrusted-derived-data">\n'
        f"{labels}\n{escape(str(text), quote=False)}\n"
        "</distilled-evidence>"
    ).strip()


def render_answer_with_sources(answer, records):
    if not records:
        return str(answer).strip()
    lines = [str(answer).strip(), "", "Sources:"]
    for record in records:
        metadata = record.get("metadata", {})
        candidates = candidate_pages(metadata)
        location = (
            f"page {metadata['page']}"
            if metadata.get("page") is not None
            else f"chapter {metadata['chapter']}"
            if metadata.get("chapter") is not None
            else f"pages {' or '.join(map(str, candidates))} (ambiguous)"
            if candidates
            else "location unavailable"
        )
        lines.append(f"- [{record['id']}] {record['source']}, {location}")
    return "\n".join(lines)


def render_claim_cited_answer(claim_citations, records):
    """Render the validated claim map and a deterministic source legend."""
    record_by_id = {record["id"]: record for record in records}
    lines = []
    for item in claim_citations:
        labels = " ".join(
            f"[{evidence_id}]"
            for evidence_id in item["supporting_ids"]
            if evidence_id in record_by_id
        )
        lines.append(f"{item['claim'].strip()} {labels}".strip())
    return render_answer_with_sources("\n".join(lines), records)
