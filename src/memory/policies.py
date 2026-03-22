"""Policies for what may enter long-term memory."""
from __future__ import annotations


def should_store_strategy(*, status: str, usable: bool) -> bool:
    """Persist only successful and usable runs."""
    return status == "completed" and usable

