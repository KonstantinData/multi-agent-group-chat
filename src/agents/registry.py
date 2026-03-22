"""Shared agent metadata."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentSpec:
    name: str
    icon: str
    color: str
    summary: str

