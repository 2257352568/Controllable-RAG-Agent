"""Pure helpers for tamper-evident human review records."""

import json
from hashlib import sha256

REVIEW_DECISIONS = {"approved", "rejected"}
REVIEW_CHECKLIST_VERSION = "2026-09-14.1"


def read_review_records(path):
    if not path.exists():
        return [], []
    records = []
    errors = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                records.append((line_number, json.loads(line)))
            except json.JSONDecodeError as error:
                errors.append(f"review line {line_number}: invalid JSON: {error.msg}")
    return records, errors


def case_content_sha256(case):
    """Hash evaluation semantics while excluding mutable review metadata."""
    payload = {
        key: value
        for key, value in case.items()
        if key not in {"review_status", "review"}
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def validate_review_records(records):
    errors = []
    required = {
        "case_id",
        "case_content_sha256",
        "decision",
        "reviewer",
        "reviewed_at",
        "checklist_version",
        "corpus_index_sha256",
        "gold_evidence_chunk_sha256",
    }
    for line_number, record in records:
        label = f"review line {line_number}"
        missing = sorted(required - record.keys())
        if missing:
            errors.append(f"{label}: missing fields: {', '.join(missing)}")
            continue
        if record["decision"] not in REVIEW_DECISIONS:
            errors.append(f"{label}: unsupported decision {record['decision']!r}")
        if record["checklist_version"] != REVIEW_CHECKLIST_VERSION:
            errors.append(
                f"{label}: checklist_version must be {REVIEW_CHECKLIST_VERSION!r}"
            )
        if not str(record["reviewer"]).strip():
            errors.append(f"{label}: reviewer must not be empty")
        digest = record["case_content_sha256"]
        if not isinstance(digest, str) or len(digest) != 64:
            errors.append(f"{label}: case_content_sha256 must be a SHA256 hex digest")
        else:
            try:
                int(digest, 16)
            except ValueError:
                errors.append(
                    f"{label}: case_content_sha256 must be a SHA256 hex digest"
                )
        corpus_digest = record["corpus_index_sha256"]
        if not isinstance(corpus_digest, str) or len(corpus_digest) != 64:
            errors.append(f"{label}: corpus_index_sha256 must be a SHA256 hex digest")
        else:
            try:
                int(corpus_digest, 16)
            except ValueError:
                errors.append(
                    f"{label}: corpus_index_sha256 must be a SHA256 hex digest"
                )
        chunk_digests = record["gold_evidence_chunk_sha256"]
        if not isinstance(chunk_digests, list) or any(
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest.lower())
            for digest in chunk_digests
        ):
            errors.append(
                f"{label}: gold_evidence_chunk_sha256 must be a list of SHA256 hex digests"
            )
        elif len(chunk_digests) != len(set(chunk_digests)):
            errors.append(f"{label}: gold evidence chunk hashes must be unique")
    return errors


def latest_reviews(records):
    """Last append-only decision wins for each case ID."""
    latest = {}
    for _, record in records:
        if record.get("case_id"):
            latest[record["case_id"]] = record
    return latest


REVIEW_PRIORITY = {
    "adversarial": 0,
    "unanswerable": 0,
    "multi_hop": 1,
    "reasoning": 2,
    "single_hop": 3,
}


def review_progress(cases, review_records, expected_corpus_sha256, next_limit=10):
    """Classify current review decisions without treating stale records as progress."""
    if int(next_limit) <= 0:
        raise ValueError("next_limit must be greater than zero")
    reviews = latest_reviews(review_records)
    grouped = {
        status: []
        for status in (
            "approved", "missing", "rejected", "stale_case", "stale_corpus",
            "invalid_approval",
        )
    }
    by_id = {case["id"]: case for case in cases}
    for case in cases:
        review = reviews.get(case["id"])
        if review is None:
            status = "missing"
        elif review.get("case_content_sha256") != case_content_sha256(case):
            status = "stale_case"
        elif review.get("corpus_index_sha256") != expected_corpus_sha256:
            status = "stale_corpus"
        elif review.get("decision") != "approved":
            status = "rejected"
        else:
            chunks = review.get("gold_evidence_chunk_sha256", [])
            invalid = (case.get("answerable") and not chunks) or (
                not case.get("answerable") and bool(chunks)
            )
            status = "invalid_approval" if invalid else "approved"
        grouped[status].append(case["id"])

    actionable = [
        case_id
        for status in ("stale_case", "stale_corpus", "invalid_approval", "missing")
        for case_id in grouped[status]
    ]
    actionable.sort(
        key=lambda case_id: (
            REVIEW_PRIORITY.get(by_id[case_id].get("category"), 99), case_id
        )
    )
    total = len(cases)
    approved = len(grouped["approved"])
    return {
        "total_cases": total,
        "approved_cases": approved,
        "remaining_cases": total - approved,
        "completion_rate": round(approved / total, 4) if total else 0.0,
        "ready_for_formal": total >= 50 and approved == total,
        "status_counts": {key: len(value) for key, value in grouped.items()},
        "case_ids_by_status": grouped,
        "next_review_ids": actionable[: int(next_limit)],
        "orphan_review_ids": sorted(set(reviews) - set(by_id)),
    }


def materialize_approved_cases(
    cases, review_records, expected_corpus_sha256=None
):
    """Verify approvals against current case hashes and add immutable provenance."""
    errors = validate_review_records(review_records)
    reviews = latest_reviews(review_records)
    approved = []
    for case in cases:
        review = reviews.get(case["id"])
        if review is None:
            errors.append(f"{case['id']}: missing human review record")
            continue
        current_hash = case_content_sha256(case)
        if review.get("case_content_sha256") != current_hash:
            errors.append(f"{case['id']}: review is stale after case content changed")
            continue
        if (
            expected_corpus_sha256
            and review.get("corpus_index_sha256") != expected_corpus_sha256
        ):
            errors.append(f"{case['id']}: review is stale after corpus index changed")
            continue
        if review.get("decision") != "approved":
            errors.append(f"{case['id']}: latest human decision is not approved")
            continue
        gold_chunks = review.get("gold_evidence_chunk_sha256", [])
        if case.get("answerable") and not gold_chunks:
            errors.append(f"{case['id']}: answerable approval requires gold evidence chunks")
            continue
        if not case.get("answerable") and gold_chunks:
            errors.append(f"{case['id']}: unanswerable approval cannot include gold evidence chunks")
            continue
        approved.append(
            {
                **case,
                "review_status": "human_approved",
                "review": {
                    "reviewer": review["reviewer"],
                    "reviewed_at": review["reviewed_at"],
                    "case_content_sha256": current_hash,
                    "corpus_index_sha256": review["corpus_index_sha256"],
                    "checklist_version": review["checklist_version"],
                    "gold_evidence_chunk_sha256": gold_chunks,
                },
            }
        )
    return approved, errors


def validate_materialized_reviews(
    cases, expected_corpus_sha256, known_chunk_sha256=None
):
    """Validate provenance embedded in a formal dataset, independent of its log."""
    errors = []
    required = {
        "reviewer",
        "reviewed_at",
        "case_content_sha256",
        "corpus_index_sha256",
        "checklist_version",
        "gold_evidence_chunk_sha256",
    }
    for case in cases:
        review = case.get("review")
        if not isinstance(review, dict):
            errors.append(f"{case['id']}: formal case is missing review provenance")
            continue
        missing = sorted(required - review.keys())
        if missing:
            errors.append(
                f"{case['id']}: review provenance missing: {', '.join(missing)}"
            )
            continue
        if review["case_content_sha256"] != case_content_sha256(case):
            errors.append(f"{case['id']}: embedded review hash does not match case")
        if review["corpus_index_sha256"] != expected_corpus_sha256:
            errors.append(f"{case['id']}: embedded review corpus hash is stale")
        if review["checklist_version"] != REVIEW_CHECKLIST_VERSION:
            errors.append(f"{case['id']}: embedded review checklist version is stale")
        if not str(review["reviewer"]).strip():
            errors.append(f"{case['id']}: embedded reviewer must not be empty")
        gold_chunks = review["gold_evidence_chunk_sha256"]
        if not isinstance(gold_chunks, list) or any(
            not isinstance(digest, str) or len(digest) != 64 for digest in gold_chunks
        ):
            errors.append(f"{case['id']}: embedded gold evidence chunks are invalid")
        elif case.get("answerable") and not gold_chunks:
            errors.append(f"{case['id']}: answerable formal case lacks gold evidence chunks")
        elif not case.get("answerable") and gold_chunks:
            errors.append(f"{case['id']}: unanswerable formal case has gold evidence chunks")
        elif known_chunk_sha256 is not None:
            unknown = sorted(set(gold_chunks) - set(known_chunk_sha256))
            if unknown:
                errors.append(
                    f"{case['id']}: gold evidence chunks are absent from current corpus: "
                    + ", ".join(unknown)
                )
    return errors
