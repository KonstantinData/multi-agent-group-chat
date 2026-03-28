"""Shared utility functions — canonical implementations.

P2-6: Eliminates duplicated _dedup_safe across 7+ modules.
"""
from __future__ import annotations

import json


def dedup_safe(items: list) -> list:
    """Deduplicate a list whose items may be dicts (unhashable).

    Uses JSON serialization as a stable key so both strings and dicts
    are handled without raising 'unhashable type: dict'.
    """
    seen: set[str] = set()
    result = []
    for item in items:
        key = (
            json.dumps(item, sort_keys=True, ensure_ascii=False)
            if isinstance(item, (dict, list))
            else str(item)
        )
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
