"""Generic finding model."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Finding:
    statement: str
    confidence: str = "mittel"
    sources: list[dict[str, str]] = field(default_factory=list)

