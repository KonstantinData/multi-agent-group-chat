"""Judge agent implementation."""
from __future__ import annotations

from src.config import get_role_model_selection
from src.orchestration.tool_policy import resolve_allowed_tools

class JudgeAgent:
    def __init__(self, name: str = "CompanyJudge") -> None:
        self.name = name
        self.model_name = get_role_model_selection(self.name)[0]
        self.allowed_tools = resolve_allowed_tools(self.name, "judge_resolution")

    def decide(self, *, section: str, critic_issues: list[str]) -> dict[str, str | bool]:
        if critic_issues:
            return {
                "accept_conservative_output": True,
                "reason": f"{section} should be kept conservative and marked as partially unresolved.",
            }
        return {"accept_conservative_output": True, "reason": "No unresolved conflict."}
