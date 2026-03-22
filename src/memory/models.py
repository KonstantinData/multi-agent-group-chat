"""Memory-side data structures."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RetrievalHit:
    name: str
    score: float
    rationale: str
    pattern_type: str = "strategy"


@dataclass(slots=True)
class StrategyPattern:
    name: str
    role: str
    industry_hint: str
    domain: str
    pattern_scope: str = "role_strategy"
    successful_queries: list[str] = field(default_factory=list)
    useful_source_types: list[str] = field(default_factory=list)
    rationale: str = ""
    score: float = 0.0
