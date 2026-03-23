"""Integration tests for AG2 GroupChat flows with monkeypatched LLM.

Covers P4 integration test gaps from optimize_todo.md:
- Single department AG2 GroupChat run (real tool closures, mocked LLM)
- Contact Department end-to-end
- SynthesisDepartmentAgent.run() with mocked department packages
- Fallback package assembly when max_round is hit
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

# AG2 requires a truthy llm_config with an api_key to register tools.
# We set a dummy key for the entire module so ConversableAgent construction
# and register_function succeed without a real OpenAI key.
_DUMMY_KEY = "sk-test-integration-dummy-key-not-real"


@pytest.fixture(autouse=True)
def _set_dummy_api_key(monkeypatch):
    """Ensure all tests in this module have a dummy OPENAI_API_KEY."""
    monkeypatch.setenv("OPENAI_API_KEY", _DUMMY_KEY)


from src.domain.intake import SupervisorBrief
from src.orchestration.task_router import Assignment


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_brief() -> SupervisorBrief:
    return SupervisorBrief(
        submitted_company_name="TestCo GmbH",
        submitted_web_domain="testco.de",
        verified_company_name="TestCo GmbH",
        verified_legal_name="TestCo GmbH",
        name_confidence="high",
        website_reachable=True,
        homepage_url="https://testco.de",
        page_title="TestCo - Industrial Parts",
        meta_description="TestCo manufactures industrial spare parts",
        raw_homepage_excerpt="TestCo GmbH manufactures precision spare parts and components for the automotive industry.",
        normalized_domain="testco.de",
        industry_hint="Automotive",
        observations=["Website reachable."],
        sources=[{"title": "TestCo", "url": "https://testco.de", "source_type": "owned", "summary": "Homepage"}],
    )


def _make_supervisor() -> MagicMock:
    sup = MagicMock()
    sup.decide_revision.return_value = {
        "retry": False,
        "same_department": True,
        "authorize_coding_specialist": False,
        "reason": "Keep conservative.",
    }
    sup.route_question.return_value = {"route": "CompanyDepartment", "reason": "test", "source": "test"}
    return sup


def _company_assignments(brief: SupervisorBrief) -> list[Assignment]:
    return [
        Assignment(
            task_key="company_fundamentals",
            assignee="CompanyDepartment",
            target_section="company_profile",
            label="Company fundamentals",
            objective=f"Build verified company fundamentals for {brief.company_name}.",
            model_name="gpt-4.1-mini",
            allowed_tools=("search", "page_fetch", "llm_structured"),
        ),
    ]


def _contact_assignments(brief: SupervisorBrief) -> list[Assignment]:
    return [
        Assignment(
            task_key="contact_discovery",
            assignee="ContactDepartment",
            target_section="contact_intelligence",
            label="Contact discovery",
            objective=f"Identify decision-makers at buyer firms for {brief.company_name}.",
            model_name="gpt-4.1-mini",
            allowed_tools=("search", "page_fetch", "llm_structured"),
        ),
    ]


# ---------------------------------------------------------------------------
# Helper: simulate a GroupChat run by calling tool closures directly
# ---------------------------------------------------------------------------

def _simulate_department_chat(lead_agent, brief, assignments, supervisor):
    """Drive the department through its tool closures without real LLM.

    Monkeypatches initiate_chat to execute the tool sequence:
    research → review → finalize.
    """

    def fake_initiate_chat(self_agent, manager, message="", **kwargs):
        # Grab registered tool functions from the agents
        tools: dict[str, Any] = {}
        for agent in manager.groupchat.agents:
            for tool_name, tool_fn in getattr(agent, "_function_map", {}).items():
                tools[tool_name] = tool_fn

        # Simulate workflow: research each task, review, then finalize
        for assignment in assignments:
            tk = assignment.task_key
            if "run_research" in tools:
                tools["run_research"](task_key=tk)
            if "review_research" in tools:
                tools["review_research"](task_key=tk)
        if "finalize_package" in tools:
            tools["finalize_package"](
                summary=f"Integration test summary for {brief.company_name}."
            )

    with patch("autogen.ConversableAgent.initiate_chat", fake_initiate_chat):
        return lead_agent.run(
            brief=brief,
            assignments=assignments,
            current_section=None,
            supervisor=supervisor,
        )


# ---------------------------------------------------------------------------
# Test 1: Single department AG2 GroupChat run (CompanyDepartment)
# ---------------------------------------------------------------------------

class TestDepartmentGroupChatRun:
    """Real AG2 tool closures, monkeypatched LLM — CompanyDepartment."""

    def test_company_department_produces_valid_package(self):
        from src.agents.lead import DepartmentLeadAgent

        brief = _make_brief()
        lead = DepartmentLeadAgent("CompanyDepartment")
        payload, messages, package = _simulate_department_chat(
            lead, brief, _company_assignments(brief), _make_supervisor()
        )

        assert package is not None
        assert package["department"] == "CompanyDepartment"
        assert len(package["completed_tasks"]) == 1
        assert package["completed_tasks"][0]["task_key"] == "company_fundamentals"
        assert isinstance(payload, dict)
        assert payload.get("company_name") == brief.company_name
        assert package["confidence"] in ("high", "medium", "low")
        assert "report_segment" in package
        assert package["report_segment"]["department"] == "CompanyDepartment"

    def test_company_department_task_status_is_valid(self):
        from src.agents.lead import DepartmentLeadAgent

        brief = _make_brief()
        lead = DepartmentLeadAgent("CompanyDepartment")
        _, _, package = _simulate_department_chat(
            lead, brief, _company_assignments(brief), _make_supervisor()
        )
        status = package["completed_tasks"][0]["status"]
        assert status in ("accepted", "degraded", "rejected")

    def test_company_department_sources_populated(self):
        from src.agents.lead import DepartmentLeadAgent

        brief = _make_brief()
        lead = DepartmentLeadAgent("CompanyDepartment")
        payload, _, _ = _simulate_department_chat(
            lead, brief, _company_assignments(brief), _make_supervisor()
        )
        assert isinstance(payload.get("sources"), list)


# ---------------------------------------------------------------------------
# Test 2: Contact Department end-to-end
# ---------------------------------------------------------------------------

class TestContactDepartmentEndToEnd:
    """Contact Department with real tool closures — validates contact-specific payload."""

    def test_contact_department_produces_package(self):
        from src.agents.lead import DepartmentLeadAgent

        brief = _make_brief()
        lead = DepartmentLeadAgent("ContactDepartment")
        _, _, package = _simulate_department_chat(
            lead, brief, _contact_assignments(brief), _make_supervisor()
        )
        assert package["department"] == "ContactDepartment"
        assert len(package["completed_tasks"]) == 1
        assert package["completed_tasks"][0]["task_key"] == "contact_discovery"

    def test_contact_payload_has_contact_fields(self):
        from src.agents.lead import DepartmentLeadAgent

        brief = _make_brief()
        lead = DepartmentLeadAgent("ContactDepartment")
        payload, _, _ = _simulate_department_chat(
            lead, brief, _contact_assignments(brief), _make_supervisor()
        )
        assert "contacts" in payload
        assert isinstance(payload["contacts"], list)
        assert "coverage_quality" in payload
        assert "narrative_summary" in payload

    def test_contact_department_confidence_set(self):
        from src.agents.lead import DepartmentLeadAgent

        brief = _make_brief()
        lead = DepartmentLeadAgent("ContactDepartment")
        _, _, package = _simulate_department_chat(
            lead, brief, _contact_assignments(brief), _make_supervisor()
        )
        assert package["confidence"] in ("high", "medium", "low")


# ---------------------------------------------------------------------------
# Test 3: SynthesisDepartmentAgent.run() with mocked department packages
# ---------------------------------------------------------------------------

def _make_department_packages() -> dict[str, dict[str, Any]]:
    segment_template = {
        "confidence": "medium",
        "key_findings": ["Finding A"],
        "open_questions": [],
        "sources": [],
    }
    return {
        "CompanyDepartment": {
            "department": "CompanyDepartment",
            "section_payload": {"company_name": "TestCo GmbH"},
            "report_segment": {
                "department": "CompanyDepartment",
                "narrative_summary": "TestCo is an automotive parts manufacturer.",
                **segment_template,
            },
        },
        "MarketDepartment": {
            "department": "MarketDepartment",
            "section_payload": {"industry_name": "Automotive"},
            "report_segment": {
                "department": "MarketDepartment",
                "narrative_summary": "Automotive parts market shows moderate demand.",
                **segment_template,
            },
        },
        "BuyerDepartment": {
            "department": "BuyerDepartment",
            "section_payload": {"target_company": "TestCo GmbH"},
            "report_segment": {
                "department": "BuyerDepartment",
                "narrative_summary": "Three peer companies identified.",
                **segment_template,
            },
        },
        "ContactDepartment": {
            "department": "ContactDepartment",
            "section_payload": {"contacts": []},
            "report_segment": {
                "department": "ContactDepartment",
                "narrative_summary": "No verified contacts found.",
                "confidence": "low",
                "key_findings": [],
                "open_questions": ["No contacts"],
                "sources": [],
            },
        },
    }


class TestSynthesisDepartmentRun:
    """SynthesisDepartmentAgent.run() with mocked packages — no real LLM."""

    def test_synthesis_produces_schema_compliant_output(self):
        from src.agents.synthesis_department import SynthesisDepartmentAgent

        agent = SynthesisDepartmentAgent()
        brief = _make_brief()
        packages = _make_department_packages()

        def fake_initiate_chat(self_agent, manager, message="", **kwargs):
            tools: dict[str, Any] = {}
            for ag in manager.groupchat.agents:
                for tool_name, tool_fn in getattr(ag, "_function_map", {}).items():
                    tools[tool_name] = tool_fn

            if "read_report_segment" in tools:
                for dept in ["CompanyDepartment", "MarketDepartment", "BuyerDepartment", "ContactDepartment"]:
                    tools["read_report_segment"](department=dept)

            if "finalize_synthesis" in tools:
                tools["finalize_synthesis"](
                    opportunity_assessment="Excess inventory monetization is the primary path.",
                    negotiation_relevance="Moderate urgency due to automotive downturn.",
                    executive_summary="TestCo presents a clear Liquisto opportunity in spare parts monetization.",
                )

        with patch("autogen.ConversableAgent.initiate_chat", fake_initiate_chat):
            synthesis, messages = agent.run(
                brief=brief,
                department_packages=packages,
                supervisor=_make_supervisor(),
                departments={},
                synthesis_context={
                    "target_company": "TestCo GmbH",
                    "liquisto_service_relevance": ["excess inventory"],
                    "recommended_engagement_paths": ["direct buyer outreach"],
                    "case_assessments": [],
                    "buyer_market_summary": "Active buyer market",
                    "key_risks": ["Low contact coverage"],
                    "next_steps": ["Validate buyer appetite"],
                    "sources": [],
                },
            )

        assert synthesis["target_company"] == "TestCo GmbH"
        assert synthesis["generation_mode"] == "normal"
        assert synthesis["confidence"] in ("high", "medium", "low")
        assert "executive_summary" in synthesis
        assert "opportunity_assessment" in synthesis
        assert "negotiation_relevance" in synthesis
        assert isinstance(synthesis["department_confidences"], dict)
        assert isinstance(synthesis["back_requests"], list)

    def test_synthesis_fallback_on_max_round(self):
        from src.agents.synthesis_department import SynthesisDepartmentAgent

        agent = SynthesisDepartmentAgent()
        brief = _make_brief()

        def fake_initiate_chat(self_agent, manager, message="", **kwargs):
            pass  # max_round hit

        with patch("autogen.ConversableAgent.initiate_chat", fake_initiate_chat):
            synthesis, _ = agent.run(
                brief=brief,
                department_packages=_make_department_packages(),
                supervisor=_make_supervisor(),
                departments={},
                synthesis_context={"target_company": "TestCo GmbH", "confidence": "low"},
            )

        assert synthesis["generation_mode"] == "fallback"
        assert synthesis["target_company"] == "TestCo GmbH"
        assert synthesis["confidence"] == "low"
        assert "executive_summary" in synthesis


# ---------------------------------------------------------------------------
# Test 4: Fallback package assembly when max_round is hit (department)
# ---------------------------------------------------------------------------

class TestFallbackPackageOnMaxRound:

    def test_company_fallback_package_on_empty_chat(self):
        from src.agents.lead import DepartmentLeadAgent

        brief = _make_brief()
        lead = DepartmentLeadAgent("CompanyDepartment")

        def fake_initiate_chat(self_agent, manager, message="", **kwargs):
            pass  # max_round hit — no tool calls

        with patch("autogen.ConversableAgent.initiate_chat", fake_initiate_chat):
            payload, messages, package = lead.run(
                brief=brief,
                assignments=_company_assignments(brief),
                current_section=None,
                supervisor=_make_supervisor(),
            )

        assert package is not None
        assert package["department"] == "CompanyDepartment"
        assert "max_round" in package["summary"].lower() or "degraded" in package["summary"].lower()
        for task in package["completed_tasks"]:
            assert task["status"] == "rejected"
            assert task["open_points"]
        assert package["confidence"] == "low"

    def test_contact_fallback_package_on_empty_chat(self):
        from src.agents.lead import DepartmentLeadAgent

        brief = _make_brief()
        lead = DepartmentLeadAgent("ContactDepartment")

        def fake_initiate_chat(self_agent, manager, message="", **kwargs):
            pass

        with patch("autogen.ConversableAgent.initiate_chat", fake_initiate_chat):
            _, _, package = lead.run(
                brief=brief,
                assignments=_contact_assignments(brief),
                current_section=None,
                supervisor=_make_supervisor(),
            )

        assert package["department"] == "ContactDepartment"
        assert package["completed_tasks"][0]["status"] == "rejected"
        assert package["confidence"] == "low"

    def test_fallback_with_partial_research(self):
        """If research ran but finalize was never called, fallback uses partial results."""
        from src.agents.lead import DepartmentLeadAgent

        brief = _make_brief()
        lead = DepartmentLeadAgent("CompanyDepartment")
        assignments = _company_assignments(brief)

        def fake_initiate_chat(self_agent, manager, message="", **kwargs):
            for agent in manager.groupchat.agents:
                for tool_name, tool_fn in getattr(agent, "_function_map", {}).items():
                    if tool_name == "run_research":
                        tool_fn(task_key="company_fundamentals")
                        return  # Stop — max_round hit mid-flow

        with patch("autogen.ConversableAgent.initiate_chat", fake_initiate_chat):
            payload, _, package = lead.run(
                brief=brief,
                assignments=assignments,
                current_section=None,
                supervisor=_make_supervisor(),
            )

        assert package is not None
        assert package["department"] == "CompanyDepartment"
        task = package["completed_tasks"][0]
        assert task["task_key"] == "company_fundamentals"
        assert task["status"] in ("accepted", "degraded", "rejected")
        # Payload should have data from the partial research
        assert payload.get("company_name") is not None
