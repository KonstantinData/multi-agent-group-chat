"""Critic agent implementation."""
from __future__ import annotations

from typing import Any

from src.config import get_role_model_selection
from src.orchestration.tool_policy import resolve_allowed_tools


TASK_POINT_RULES: dict[str, list[tuple[str, callable]]] = {
    "company_fundamentals": [
        ("verified_identity", lambda payload: payload.get("company_name", "n/v") != "n/v"),
        ("website_match", lambda payload: payload.get("website", "n/v") != "n/v"),
        ("industry_classification", lambda payload: payload.get("industry", "n/v") != "n/v"),
        (
            "offer_or_business_description",
            lambda payload: bool(payload.get("description", "").strip()) or bool(payload.get("products_and_services")),
        ),
    ],
    "economic_commercial_situation": [
        ("economic_assessment", lambda payload: payload.get("economic_situation", {}).get("assessment", "n/v") != "n/v"),
        ("commercial_signals", lambda payload: bool(payload.get("economic_situation", {}).get("recent_events")) or bool(payload.get("economic_situation", {}).get("inventory_signals"))),
    ],
    "market_situation": [
        ("industry_name", lambda payload: payload.get("industry_name", "n/v") != "n/v"),
        ("market_assessment", lambda payload: payload.get("assessment", "n/v") != "n/v"),
        (
            "market_signals",
            lambda payload: bool(payload.get("key_trends")) or payload.get("demand_outlook", "n/v") != "n/v",
        ),
    ],
    "peer_companies": [
        ("target_company", lambda payload: payload.get("target_company", "n/v") != "n/v"),
        (
            "peer_landscape",
            lambda payload: bool(payload.get("peer_competitors", {}).get("companies"))
            or "no " in str(payload.get("peer_competitors", {}).get("assessment", "")).lower(),
        ),
    ],
    "product_asset_scope": [
        ("product_asset_scope", lambda payload: bool(payload.get("product_asset_scope"))),
    ],
    "monetization_redeployment": [
        (
            "buyer_or_path_signal",
            lambda payload: bool(payload.get("downstream_buyers", {}).get("companies"))
            or bool(payload.get("monetization_paths"))
            or bool(payload.get("redeployment_paths")),
        ),
        ("target_company", lambda payload: payload.get("target_company", "n/v") != "n/v"),
    ],
    "repurposing_circularity": [
        ("repurposing_signal", lambda payload: bool(payload.get("repurposing_signals"))),
    ],
    "analytics_operational_improvement": [
        ("analytics_signal", lambda payload: bool(payload.get("analytics_signals"))),
    ],
}


class CriticAgent:
    def __init__(self, name: str = "CompanyCritic") -> None:
        self.name = name
        self.model_name = get_role_model_selection(self.name)[0]
        self.allowed_tools = resolve_allowed_tools(self.name, "critic_review")

    def review(
        self,
        *,
        task_key: str,
        section: str,
        objective: str,
        payload: dict,
        report: dict[str, Any] | None = None,
        role_memory: list[dict[str, Any]] | None = None,
    ) -> dict:
        rules = TASK_POINT_RULES.get(task_key, [])
        accepted_points: list[str] = []
        rejected_points: list[str] = []
        missing_points: list[str] = []
        issues: list[str] = []

        for point_name, predicate in rules:
            try:
                satisfied = bool(predicate(payload))
            except Exception:
                satisfied = False
            if satisfied:
                accepted_points.append(point_name)
            else:
                rejected_points.append(point_name)
                missing_points.append(point_name)
                issues.append(f"Point '{point_name}' is still insufficient for {task_key}.")

        sources = payload.get("sources", []) if isinstance(payload, dict) else []
        if not sources:
            issues.append("No supporting source recorded.")
            missing_points.append("supporting_sources")
        external_sources = [
            source for source in sources if isinstance(source, dict) and source.get("source_type") not in {"owned", "first_party"}
        ]
        evidence_strength = "strong" if len(external_sources) >= 2 else "moderate" if sources else "weak"

        method_issue = False
        if report:
            queries_used = report.get("queries_used", [])
            search_calls = report.get("usage", {}).get("search_calls", 0)
            if rejected_points and search_calls and not external_sources and queries_used:
                method_issue = True

        approved = bool(rules) and not rejected_points and evidence_strength != "weak"
        if not rules:
            approved = not issues

        feedback_to_worker = []
        for point_name in rejected_points:
            feedback_to_worker.append(
                {
                    "point": point_name,
                    "status": "revise",
                    "guidance": f"Rework the missing or weak point '{point_name}' so it directly satisfies the task objective.",
                }
            )

        coding_brief = {
            "task_key": task_key,
            "objective": objective,
            "rejected_points": rejected_points,
            "missing_points": list(dict.fromkeys(missing_points)),
            "issues": issues,
            "method_issue": method_issue,
            "research_gap": (
                "The search and evidence path needs to be improved before the same worker retries the open points."
                if method_issue
                else "Direct worker revision should be sufficient."
            ),
        }

        return {
            "approved": approved,
            "issues": issues,
            "accepted_points": accepted_points,
            "rejected_points": rejected_points,
            "missing_points": list(dict.fromkeys(missing_points)),
            "evidence_strength": evidence_strength,
            "method_issue": method_issue,
            "revision_instructions": [
                "Keep already accepted points stable.",
                "Revise only the rejected or missing points.",
                "Downgrade unsupported claims if stronger evidence cannot be found.",
            ]
            if issues
            else [],
            "feedback_to_worker": feedback_to_worker,
            "coding_brief": coding_brief,
            "field_issues": [],
            "objective": objective,
            "role_memory_used": bool(role_memory),
        }
