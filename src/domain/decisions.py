"""Decision-side domain models."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class OpportunityAssessment:
    option: str
    summary: str
    arguments: list[dict[str, str]] = field(default_factory=list)

