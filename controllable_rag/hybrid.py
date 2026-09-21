"""Deterministic rank fusion primitives for hybrid retrieval."""


def reciprocal_rank_fusion(ranked_lists, *, limit, rank_constant=60):
    """Fuse ranked document-key lists with reciprocal rank fusion.

    Each retriever contributes ``1 / (rank_constant + rank)`` once per key.
    Ties are resolved by first appearance and then the key representation so
    repeated runs over identical inputs produce identical output.
    """
    if limit <= 0:
        raise ValueError("RRF limit must be greater than zero")
    if rank_constant < 0:
        raise ValueError("RRF rank_constant must be non-negative")
    if not ranked_lists:
        raise ValueError("RRF requires at least one ranked list")

    scores = {}
    first_seen = {}
    appearance = 0
    for ranked in ranked_lists:
        seen_in_list = set()
        for rank, key in enumerate(ranked, 1):
            if key in seen_in_list:
                continue
            seen_in_list.add(key)
            if key not in first_seen:
                first_seen[key] = appearance
                appearance += 1
            scores[key] = scores.get(key, 0.0) + 1.0 / (rank_constant + rank)

    ordered = sorted(
        scores,
        key=lambda key: (-scores[key], first_seen[key], repr(key)),
    )[:limit]
    return [(key, scores[key]) for key in ordered]
