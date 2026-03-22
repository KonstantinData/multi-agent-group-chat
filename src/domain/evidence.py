"""Evidence models."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EvidenceRecord:
    title: str
    url: str
    source_type: str
    summary: str = ""

