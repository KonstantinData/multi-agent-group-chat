"""Coding/search assistant used as a targeted escalation."""
from __future__ import annotations

from src.config import get_role_model_selection
from src.domain.intake import SupervisorBrief
from src.orchestration.tool_policy import resolve_allowed_tools
from src.research.extract import extract_product_keywords, infer_industry


class CodingAssistantAgent:
    def __init__(self, name: str = "CompanyCodingSpecialist") -> None:
        self.name = name
        self.model_name = get_role_model_selection(self.name)[0]
        self.allowed_tools = resolve_allowed_tools(self.name, "query_refinement")

    def suggest_queries(
        self,
        *,
        section: str,
        brief: SupervisorBrief,
        issues: list[str],
        review: dict | None = None,
        coding_brief: dict | None = None,
    ) -> dict:
        product_keywords = extract_product_keywords(brief.raw_homepage_excerpt)
        industry_hint = infer_industry(brief.page_title, brief.meta_description, brief.raw_homepage_excerpt)
        base = product_keywords[:3] or [brief.company_name]
        if section == "industry_analysis":
            queries = [f"{' '.join(base)} industry report demand"] + [f"{brief.company_name} market report", f"{industry_hint} market outlook"]
        else:
            queries = [f"{' '.join(base)} buyers distributors"] + [f"{brief.company_name} customers aftermarket"]
        return {
            "section": section,
            "issues": issues,
            "query_overrides": queries,
            "revision_focus": list((review or {}).get("rejected_points", [])),
            "coding_brief": coding_brief or {},
            "summary": "Refined search path generated for a second attempt.",
            "model_name": self.model_name,
            "allowed_tools": list(self.allowed_tools),
        }
