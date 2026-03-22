"""Convenience retrieval helpers."""
from __future__ import annotations

from typing import Any

from src.memory.long_term_store import FileLongTermMemoryStore


def retrieve_strategies(
    store: FileLongTermMemoryStore,
    *,
    domain: str,
    industry_hint: str = "",
    role: str = "",
    limit: int = 5,
) -> list[dict[str, Any]]:
    return store.retrieve(domain=domain, industry_hint=industry_hint, role=role, limit=limit)
