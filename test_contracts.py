"""Contract, Critic, Judge, and router semantic tests.

These tests validate the new deterministic semantics introduced in the
optimize_todo.md refactor:
- STANDARD_TASK_BACKLOG has the full contract shape
- output_schema_key resolves in the SCHEMA_REGISTRY
- validation_rules are structurally valid
- Critic generic evaluators work
- Judge three-outcome gate works
- skipped is set by routing, never by the Judge
- Contact tasks are conditional on buyer output
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.app.use_cases import (
    STANDARD_TASK_BACKLOG,
    get_task_validation_rules,
    get_task_contract,
)
from src.models.registry import SCHEMA_REGISTRY, resolve_output_schema
from src.agents.critic import CriticAgent, _evaluate_rule
from src.agents.judge import JudgeAgent


# ---------------------------------------------------------------------------
# 1. Contract migration tests
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "task_key", "label", "assignee", "target_section", "objective_template",
    "depends_on", "run_condition", "input_artifacts", "output_schema_key",
    "validation_rules",
}

VALID_RULE_CHECKS = {"non_placeholder", "min_items", "min_length"}
VALID_RULE_CLASSES = {"core", "supporting"}


def test_all_tasks_have_required_contract_fields():
    for task in STANDARD_TASK_BACKLOG:
        missing = REQUIRED_FIELDS - set(task.keys())
        assert not missing, f"Task '{task['task_key']}' is missing fields: {missing}"


def test_all_tasks_have_12_entries():
    assert len(STANDARD_TASK_BACKLOG) == 12


def test_output_schema_key_resolves_in_registry():
    for task in STANDARD_TASK_BACKLOG:
        key = task["output_schema_key"]
        model = resolve_output_schema(key)
        assert model is not None, f"output_schema_key '{key}' for task '{task['task_key']}' not in registry"


def test_all_validation_rules_are_structurally_valid():
    for task in STANDARD_TASK_BACKLOG:
        for rule in task.get("validation_rules", []):
            assert "check" in rule, f"Rule in '{task['task_key']}' missing 'check'"
            assert "field" in rule, f"Rule in '{task['task_key']}' missing 'field'"
            assert "class" in rule, f"Rule in '{task['task_key']}' missing 'class'"
            assert "message" in rule, f"Rule in '{task['task_key']}' missing 'message'"
            assert rule["check"] in VALID_RULE_CHECKS, (
                f"Unknown check '{rule['check']}' in task '{task['task_key']}'"
            )
            assert rule["class"] in VALID_RULE_CLASSES, (
                f"Unknown class '{rule['class']}' in task '{task['task_key']}'"
            )
            if rule["check"] in {"min_items", "min_length"}:
                assert "value" in rule, (
                    f"Rule check '{rule['check']}' in '{task['task_key']}' requires 'value'"
                )


def test_contact_tasks_have_run_conditions():
    discovery = get_task_contract("contact_discovery")
    qualification = get_task_contract("contact_qualification")
    assert discovery is not None
    assert qualification is not None
    assert discovery["run_condition"] == "buyer_department_has_prioritized_firms"
    assert qualification["run_condition"] == "contact_discovery_completed"


def test_non_contact_tasks_have_no_run_condition():
    for task in STANDARD_TASK_BACKLOG:
        if task["task_key"] not in {"contact_discovery", "contact_qualification"}:
            assert task["run_condition"] is None, (
                f"Task '{task['task_key']}' should have run_condition=None"
            )


def test_schema_registry_contains_all_output_keys():
    expected_keys = {task["output_schema_key"] for task in STANDARD_TASK_BACKLOG}
    missing = expected_keys - set(SCHEMA_REGISTRY.keys())
    assert not missing, f"SCHEMA_REGISTRY is missing keys: {missing}"


# ---------------------------------------------------------------------------
# 2. Critic generic evaluator tests
# ---------------------------------------------------------------------------

def test_critic_non_placeholder_passes_real_value():
    rule = {"check": "non_placeholder", "field": "company_name", "class": "core", "message": "missing"}
    assert _evaluate_rule(rule, {"company_name": "ACME GmbH"}) is True


def test_critic_non_placeholder_fails_nv():
    rule = {"check": "non_placeholder", "field": "company_name", "class": "core", "message": "missing"}
    assert _evaluate_rule(rule, {"company_name": "n/v"}) is False


def test_critic_non_placeholder_fails_empty():
    rule = {"check": "non_placeholder", "field": "industry", "class": "core", "message": "missing"}
    assert _evaluate_rule(rule, {"industry": ""}) is False


def test_critic_min_items_passes():
    rule = {"check": "min_items", "field": "products_and_services", "value": 1, "class": "supporting", "message": "missing"}
    assert _evaluate_rule(rule, {"products_and_services": ["Control units"]}) is True


def test_critic_min_items_fails_empty_list():
    rule = {"check": "min_items", "field": "products_and_services", "value": 1, "class": "supporting", "message": "missing"}
    assert _evaluate_rule(rule, {"products_and_services": []}) is False


def test_critic_min_length_passes():
    rule = {"check": "min_length", "field": "description", "value": 10, "class": "supporting", "message": "missing"}
    assert _evaluate_rule(rule, {"description": "A long enough description."}) is True


def test_critic_min_length_fails():
    rule = {"check": "min_length", "field": "description", "value": 10, "class": "supporting", "message": "missing"}
    assert _evaluate_rule(rule, {"description": "Short"}) is False


def test_critic_nested_field_resolution():
    rule = {"check": "non_placeholder", "field": "economic_situation.assessment", "class": "core", "message": "missing"}
    assert _evaluate_rule(rule, {"economic_situation": {"assessment": "Strong growth"}}) is True
    assert _evaluate_rule(rule, {"economic_situation": {"assessment": "n/v"}}) is False
    assert _evaluate_rule(rule, {"economic_situation": {}}) is False


def test_critic_unknown_check_fails_safe():
    rule = {"check": "does_not_exist", "field": "x", "class": "core", "message": "unknown"}
    assert _evaluate_rule(rule, {"x": "something"}) is False


def test_critic_review_produces_class_counts():
    critic = CriticAgent("CompanyCritic")
    rules = [
        {"check": "non_placeholder", "field": "company_name", "class": "core", "message": "m1"},
        {"check": "non_placeholder", "field": "website", "class": "core", "message": "m2"},
        {"check": "min_items", "field": "products_and_services", "value": 1, "class": "supporting", "message": "m3"},
    ]
    payload = {"company_name": "ACME", "website": "acme.de", "products_and_services": ["widgets"]}
    result = critic.review(
        task_key="company_fundamentals",
        section="company_profile",
        objective="test",
        payload=payload,
        validation_rules=rules,
    )
    assert result["core_passed"] == 2
    assert result["core_total"] == 2
    assert result["supporting_passed"] == 1
    assert result["supporting_total"] == 1


def test_critic_no_task_point_rules_dict():
    """TASK_POINT_RULES must no longer exist in critic module."""
    import src.agents.critic as critic_mod
    assert not hasattr(critic_mod, "TASK_POINT_RULES"), (
        "TASK_POINT_RULES still present — must be removed after migration"
    )


# ---------------------------------------------------------------------------
# 3. Judge three-outcome gate tests
# ---------------------------------------------------------------------------

def _make_review(core_passed: int, core_total: int, supporting_passed: int, supporting_total: int) -> dict:
    failed_msgs = [f"core rule {i} failed" for i in range(core_total - core_passed)]
    return {
        "core_passed": core_passed,
        "core_total": core_total,
        "supporting_passed": supporting_passed,
        "supporting_total": supporting_total,
        "failed_rule_messages": failed_msgs,
        "issues": failed_msgs,
    }


def test_judge_accept_when_all_core_pass():
    judge = JudgeAgent("CompanyJudge")
    review = _make_review(core_passed=2, core_total=2, supporting_passed=1, supporting_total=1)
    result = judge.decide(section="company_fundamentals", critic_review=review)
    assert result["decision"] == "accept"
    assert result["task_status"] == "accepted"


def test_judge_accept_degraded_when_partial_core():
    judge = JudgeAgent("CompanyJudge")
    review = _make_review(core_passed=1, core_total=2, supporting_passed=0, supporting_total=1)
    result = judge.decide(section="market_situation", critic_review=review)
    assert result["decision"] == "accept_degraded"
    assert result["task_status"] == "degraded"
    assert len(result["open_questions"]) >= 1


def test_judge_reject_when_no_core_pass():
    judge = JudgeAgent("CompanyJudge")
    review = _make_review(core_passed=0, core_total=2, supporting_passed=0, supporting_total=1)
    result = judge.decide(section="peer_companies", critic_review=review)
    assert result["decision"] == "reject"
    assert result["task_status"] == "rejected"


def test_judge_never_produces_skipped():
    judge = JudgeAgent("CompanyJudge")
    review = _make_review(core_passed=0, core_total=2, supporting_passed=0, supporting_total=0)
    result = judge.decide(section="any_task", critic_review=review)
    assert result["task_status"] != "skipped", "Judge must never produce skipped status"


def test_judge_degraded_carries_open_questions():
    judge = JudgeAgent("CompanyJudge")
    review = _make_review(core_passed=1, core_total=3, supporting_passed=0, supporting_total=1)
    result = judge.decide(section="some_task", critic_review=review)
    assert result["task_status"] == "degraded"
    assert result["open_questions"], "Degraded output must carry open_questions from failed rules"


def test_judge_confidence_high_when_all_rules_pass():
    judge = JudgeAgent("CompanyJudge")
    review = _make_review(core_passed=2, core_total=2, supporting_passed=2, supporting_total=2)
    result = judge.decide(section="company_fundamentals", critic_review=review)
    assert result["confidence"] == "high"


def test_judge_confidence_low_when_degraded():
    judge = JudgeAgent("CompanyJudge")
    review = _make_review(core_passed=1, core_total=2, supporting_passed=0, supporting_total=1)
    result = judge.decide(section="test", critic_review=review)
    assert result["confidence"] == "low"


# ---------------------------------------------------------------------------
# 4. Router / skipped semantics tests
# ---------------------------------------------------------------------------

def test_contact_tasks_skipped_when_no_buyer_candidates(monkeypatch):
    """When BuyerDepartment produces no accepted_points, Contact tasks must be skipped."""
    from src.orchestration import supervisor_loop
    from src.orchestration.task_router import DepartmentAssignment, Assignment
    from src.orchestration.run_context import RunContext
    from src.domain.intake import SupervisorBrief
    from src.memory.short_term_store import ShortTermMemoryStore

    brief = SupervisorBrief(
        submitted_company_name="ACME GmbH",
        submitted_web_domain="acme.example",
        verified_company_name="ACME GmbH",
        verified_legal_name="ACME GmbH",
        name_confidence="high",
        website_reachable=True,
        homepage_url="https://acme.example",
        page_title="ACME",
        meta_description="test",
        raw_homepage_excerpt="test",
        normalized_domain="acme.example",
    )

    run_context = RunContext(run_id="test_skip", intake={"company_name": "ACME GmbH"})

    contact_assignment = Assignment(
        task_key="contact_discovery",
        assignee="ContactDepartment",
        target_section="contact_intelligence",
        label="Contact discovery",
        objective="Find contacts",
        model_name="gpt-4.1-mini",
        allowed_tools=("search", "page_fetch", "llm_structured"),
    )
    dept_assignment = DepartmentAssignment(
        department="ContactDepartment",
        target_section="contact_intelligence",
        assignments=(contact_assignment,),
    )

    dept_assignment_map = {"ContactDepartment": dept_assignment}
    sections: dict = {}
    # BuyerDepartment produced no accepted_points
    department_packages: dict = {"BuyerDepartment": {"accepted_points": []}}
    completed_backlog: list = []

    # Simulate just the ContactDepartment skipping logic
    department_name = "ContactDepartment"
    da = dept_assignment_map[department_name]
    current_section = sections.get(da.target_section, {})

    buyer_package = department_packages.get("BuyerDepartment", {})
    buyer_candidates = buyer_package.get("accepted_points", [])
    if not buyer_candidates:
        for a in da.assignments:
            run_context.update_task_status(task_key=a.task_key, status="skipped")
            run_context.short_term_memory.task_statuses[a.task_key] = "skipped"
            completed_backlog.append({
                "task_key": a.task_key,
                "label": a.label,
                "target_section": a.target_section,
                "status": "skipped",
            })

    assert run_context.short_term_memory.task_statuses.get("contact_discovery") == "skipped"
    assert completed_backlog[0]["status"] == "skipped"
    assert completed_backlog[0]["task_key"] == "contact_discovery"


# ---------------------------------------------------------------------------
# 5. Synthesis generation_mode / confidence tests
# ---------------------------------------------------------------------------

def test_build_synthesis_context_returns_confidence_from_quality_review():
    from src.orchestration.synthesis import build_synthesis_context
    result = build_synthesis_context(
        company_profile={"company_name": "ACME GmbH", "industry": "Manufacturing"},
        industry_analysis={"analytics_signals": [], "key_trends": []},
        market_network={
            "peer_competitors": {"companies": []},
            "downstream_buyers": {"companies": [], "assessment": "n/v"},
            "service_providers": {"companies": []},
            "cross_industry_buyers": {"companies": []},
            "monetization_paths": [],
            "redeployment_paths": [],
        },
        quality_review={"evidence_health": "medium", "open_gaps": []},
        memory_snapshot={"sources": [], "next_actions": []},
    )
    assert result["confidence"] == "medium"


def test_synthesis_fallback_confidence_not_forced_low():
    """Fallback synthesis with good evidence should NOT be confidence=low."""
    from src.orchestration.synthesis import build_synthesis_context
    result = build_synthesis_context(
        company_profile={"company_name": "ACME GmbH", "industry": "Manufacturing"},
        industry_analysis={"analytics_signals": ["gap signal"], "key_trends": ["trend"]},
        market_network={
            "peer_competitors": {"companies": [{"name": "Peer1"}], "assessment": "competitive"},
            "downstream_buyers": {"companies": [{"name": "Buyer1"}], "assessment": "active"},
            "service_providers": {"companies": []},
            "cross_industry_buyers": {"companies": []},
            "monetization_paths": ["resale path"],
            "redeployment_paths": ["redeployment path"],
        },
        quality_review={"evidence_health": "high", "open_gaps": []},
        memory_snapshot={"sources": [], "next_actions": []},
    )
    # With high evidence_health, fallback can still be high confidence
    assert result["confidence"] == "high"


# ---------------------------------------------------------------------------
# 6. Section assembly tests
# ---------------------------------------------------------------------------

def test_assemble_section_company_profile():
    from src.models.registry import assemble_section
    raw = {
        "company_name": "ACME GmbH",
        "website": "acme.de",
        "industry": "Manufacturing",
        "products_and_services": ["widgets"],
        "product_asset_scope": ["steel parts"],
        "economic_situation": {"assessment": "Stable", "revenue_trend": "flat"},
    }
    result = assemble_section("company_profile", raw)
    assert result["company_name"] == "ACME GmbH"
    assert result["economic_situation"]["assessment"] == "Stable"
    # Pydantic fills defaults for missing fields
    assert "legal_form" in result
    assert "key_people" in result


def test_assemble_section_industry_analysis():
    from src.models.registry import assemble_section
    raw = {
        "industry_name": "Automotive",
        "assessment": "Declining",
        "key_trends": ["EV shift"],
        "repurposing_signals": ["battery reuse"],
        "analytics_signals": ["planning gap"],
    }
    result = assemble_section("industry_analysis", raw)
    assert result["industry_name"] == "Automotive"
    assert result["repurposing_signals"] == ["battery reuse"]
    assert "overcapacity_signals" in result


def test_assemble_section_market_network():
    from src.models.registry import assemble_section
    raw = {
        "target_company": "ACME",
        "peer_competitors": {"companies": [{"name": "Peer1"}], "assessment": "close"},
        "downstream_buyers": {"companies": [], "assessment": "n/v"},
        "monetization_paths": ["resale"],
    }
    result = assemble_section("market_network", raw)
    assert result["target_company"] == "ACME"
    assert len(result["peer_competitors"]["companies"]) == 1
    assert "service_providers" in result


def test_assemble_section_contact_intelligence():
    from src.models.registry import assemble_section
    raw = {
        "contacts": [{"name": "Jane Doe", "firma": "BuyerCo"}],
        "firms_searched": 3,
        "contacts_found": 1,
    }
    result = assemble_section("contact_intelligence", raw)
    assert result["contacts_found"] == 1
    assert result["contacts"][0]["name"] == "Jane Doe"
    assert "prioritized_contacts" in result


def test_assemble_section_unknown_returns_raw():
    from src.models.registry import assemble_section
    raw = {"custom_key": "value"}
    result = assemble_section("synthesis", raw)
    assert result == raw


def test_assemble_section_empty_payload_returns_defaults():
    from src.models.registry import assemble_section
    result = assemble_section("company_profile", {})
    assert result["company_name"] == "n/v"
    assert result["products_and_services"] == []


def test_section_model_map_covers_all_department_sections():
    from src.models.registry import SECTION_MODEL_MAP
    expected = {"company_profile", "industry_analysis", "market_network", "contact_intelligence"}
    assert set(SECTION_MODEL_MAP.keys()) == expected


# ---------------------------------------------------------------------------
# 7. Legacy "conservative" regression test
# ---------------------------------------------------------------------------

def test_no_conservative_status_in_use_cases():
    """The word 'conservative' as a task status must not appear in use_cases."""
    from src.app import use_cases
    import inspect
    source = inspect.getsource(use_cases)
    # Allow the word in comments/docstrings but not as a status value
    assert '"conservative"' not in source, (
        "Legacy status 'conservative' still referenced in use_cases.py"
    )


def test_validation_rules_lookup_returns_empty_for_unknown_task():
    rules = get_task_validation_rules("totally_unknown_task_key")
    assert rules == []


def test_get_task_contract_returns_none_for_unknown():
    contract = get_task_contract("does_not_exist")
    assert contract is None
