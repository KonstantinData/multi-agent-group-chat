"""Buyer-path domain models."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class BuyerPath:
    name: str
    relevance: str
    route_type: str
    details: str = "n/v"
    sources: list[dict[str, str]] = field(default_factory=list)

