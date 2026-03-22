"""Market-oriented domain models."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MarketSignal:
    label: str
    rationale: str
    sources: list[dict[str, str]] = field(default_factory=list)

