"""Deterministic text transformations used by graph nodes."""

import re


def apply_entity_mapping(plan, mapping):
    """Replace anonymized variables in plan steps without substring collisions."""
    resolved_steps = []
    for step in plan:
        resolved = step
        for variable, entity in sorted(mapping.items(), key=lambda item: -len(item[0])):
            resolved = re.sub(
                rf"\b{re.escape(str(variable))}\b",
                lambda _match, replacement=str(entity): replacement,
                resolved,
            )
        resolved_steps.append(resolved)
    return resolved_steps
