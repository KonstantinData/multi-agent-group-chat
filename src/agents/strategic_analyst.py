"""Cross-domain strategic analyst agent."""
from __future__ import annotations

from src.config import get_role_model_selection
from src.orchestration.tool_policy import resolve_allowed_tools


class CrossDomainStrategicAnalystAgent:
    name = "CrossDomainStrategicAnalyst"

    def __init__(self) -> None:
        self.model_name = get_role_model_selection(self.name)[0]
        self.allowed_tools = resolve_allowed_tools(self.name, "liquisto_opportunity_assessment")
