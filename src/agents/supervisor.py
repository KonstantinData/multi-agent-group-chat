"""Supervisor agent implementation."""
from __future__ import annotations

from dataclasses import asdict

from src.app.use_cases import build_standard_scope
from src.config import get_role_model_selection
from src.domain.intake import IntakeRequest, SupervisorBrief
from src.orchestration.tool_policy import resolve_allowed_tools
from src.research.extract import infer_industry
from src.research.tools import build_company_research


class SupervisorAgent:
    name = "Supervisor"

    def __init__(self) -> None:
        self.model_name = get_role_model_selection(self.name)[0]
        self.allowed_tools = resolve_allowed_tools(self.name, "intake_normalization")

    def opening_message(self) -> str:
        return build_standard_scope()

    def build_intake_brief(self, intake: IntakeRequest) -> tuple[SupervisorBrief, dict]:
        research = build_company_research(intake.web_domain, intake.company_name)
        snapshot = research["snapshot"]
        industry_hint = infer_industry(
            title=str(snapshot.get("title", "")),
            description=str(snapshot.get("meta_description", "")),
            text=str(research.get("summary", "")),
        )
        brief = SupervisorBrief(
            submitted_company_name=intake.company_name,
            submitted_web_domain=intake.web_domain,
            verified_company_name=str(research.get("verified_company_name", intake.company_name)),
            verified_legal_name=str(research.get("verified_legal_name", "")),
            name_confidence=str(research.get("name_confidence", "low")),
            website_reachable=bool(snapshot.get("reachable")),
            homepage_url=str(research["homepage_url"]),
            page_title=str(snapshot.get("title", "")),
            meta_description=str(snapshot.get("meta_description", "")),
            raw_homepage_excerpt=str(research["summary"]),
            normalized_domain=str(research["normalized_domain"]),
            industry_hint=industry_hint,
            observations=[
                "Website reachable." if snapshot.get("reachable") else "Website not reachable.",
                f"Verified company name: {research.get('verified_company_name', intake.company_name)}.",
                f"Name confidence: {research.get('name_confidence', 'low')}.",
            ],
            sources=[
                {
                    "title": str(snapshot.get("title") or research.get("verified_company_name") or intake.company_name),
                    "url": str(research["homepage_url"]),
                    "source_type": "owned",
                    "summary": str(research["summary"]),
                }
            ],
        )
        message_payload = {
            "section": "supervisor_brief",
            "payload": asdict(brief),
            "status": "ready_for_department_routing",
        }
        return brief, message_payload

    def decide_revision(self, *, task_key: str, review: dict, attempt: int) -> dict[str, str | bool]:
        rejected_points = list(review.get("rejected_points", []))
        method_issue = bool(review.get("method_issue"))
        if rejected_points and attempt < 2:
            return {
                "retry": True,
                "same_department": True,
                "authorize_coding_specialist": method_issue,
                "reason": f"Revise {task_key} for unresolved points: {', '.join(rejected_points)}.",
            }
        return {
            "retry": False,
            "same_department": True,
            "authorize_coding_specialist": False,
            "reason": f"Keep {task_key} conservative and document the remaining gap.",
        }

    def accept_department_package(self, *, department: str, package: dict) -> dict[str, str | bool]:
        completed_tasks = package.get("completed_tasks", [])
        open_questions = package.get("open_questions", [])
        has_payload = bool(package.get("section_payload"))
        accepted = has_payload and bool(completed_tasks)
        reason = (
            f"{department} package accepted for synthesis."
            if accepted
            else f"{department} package remains incomplete and should be marked conservative."
        )
        return {
            "accepted": accepted,
            "reason": reason,
            "open_questions_present": bool(open_questions),
        }

    def accept_synthesis(self, *, synthesis_payload: dict) -> dict[str, str | bool]:
        target_company = synthesis_payload.get("target_company", "n/v")
        accepted = target_company != "n/v"
        return {
            "accepted": accepted,
            "reason": "Cross-domain synthesis accepted." if accepted else "Cross-domain synthesis incomplete.",
        }

    def route_follow_up(self, *, question: str) -> dict[str, str]:
        """Route a UI follow-up question to the responsible department."""
        return self.route_question(question=question, source="user_ui")

    def route_question(self, *, question: str, source: str = "user_ui") -> dict[str, str]:
        """Unified router for both synthesis back-requests and UI follow-up questions.

        source: "synthesis" | "user_ui"
        """
        lowered = question.lower()
        if any(token in lowered for token in ["contact", "ansprechpartner", "person", "entscheider", "outreach", "linkedin", "name", "rolle"]):
            route = "ContactDepartment"
        elif any(token in lowered for token in ["market", "demand", "supply", "capacity", "circular", "analytics", "markt"]):
            route = "MarketDepartment"
        elif any(token in lowered for token in ["buyer", "buyers", "resale", "redeployment", "aftermarket", "competitor", "käufer"]):
            route = "BuyerDepartment"
        elif any(token in lowered for token in ["opportunity", "liquisto", "meeting", "next step", "synthesis", "briefing", "zusammenfassung"]):
            route = "SynthesisDepartment"
        else:
            route = "CompanyDepartment"
        return {
            "route": route,
            "reason": f"Question routed to {route} based on dominant topic.",
            "source": source,
        }
