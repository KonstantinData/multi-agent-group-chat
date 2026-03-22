"""Final briefing model."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Briefing:
    target_company: str
    executive_summary: str
    next_steps: list[str] = field(default_factory=list)
