"""Run-based follow-up loading, routing, and answering."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.exporters.json_export import export_follow_up
from src.models.schemas import FollowUpAnswer


ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "artifacts" / "runs"


def load_run_artifact(run_id: str) -> dict[str, Any]:
    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"Run '{run_id}' was not found.")
    pipeline_data = json.loads((run_dir / "pipeline_data.json").read_text(encoding="utf-8"))
    run_context = json.loads((run_dir / "run_context.json").read_text(encoding="utf-8"))
    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "pipeline_data": pipeline_data,
        "run_context": run_context,
    }


def _company_answer(question: str, pipeline_data: dict[str, Any], run_context: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    profile = pipeline_data.get("company_profile", {})
    package = run_context.get("short_term_memory", {}).get("department_packages", {}).get("CompanyDepartment", {})
    evidence = [
        profile.get("description", ""),
        *profile.get("product_asset_scope", [])[:3],
        profile.get("economic_situation", {}).get("assessment", ""),
    ]
    unresolved = package.get("open_questions", [])[:3]
    answer = (
        f"Company follow-up for '{question}': "
        f"{profile.get('company_name', 'The target company')} is described as {profile.get('description', 'n/v')}. "
        f"Relevant visible goods or stock signals include {', '.join(profile.get('product_asset_scope', [])[:2]) or 'n/v'}. "
        f"Economic context: {profile.get('economic_situation', {}).get('assessment', 'n/v')}."
    )
    return answer, [item for item in evidence if item], unresolved


def _market_answer(question: str, pipeline_data: dict[str, Any], run_context: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    analysis = pipeline_data.get("industry_analysis", {})
    package = run_context.get("short_term_memory", {}).get("department_packages", {}).get("MarketDepartment", {})
    evidence = [
        analysis.get("assessment", ""),
        analysis.get("demand_outlook", ""),
        *analysis.get("repurposing_signals", [])[:2],
        *analysis.get("analytics_signals", [])[:2],
    ]
    unresolved = package.get("open_questions", [])[:3]
    answer = (
        f"Market follow-up for '{question}': "
        f"Industry assessment: {analysis.get('assessment', 'n/v')}. "
        f"Demand outlook: {analysis.get('demand_outlook', 'n/v')}. "
        f"Repurposing or analytics signals: "
        f"{', '.join((analysis.get('repurposing_signals', []) + analysis.get('analytics_signals', []))[:3]) or 'n/v'}."
    )
    return answer, [item for item in evidence if item], unresolved


def _buyer_answer(question: str, pipeline_data: dict[str, Any], run_context: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    network = pipeline_data.get("market_network", {})
    package = run_context.get("short_term_memory", {}).get("department_packages", {}).get("BuyerDepartment", {})
    peers = network.get("peer_competitors", {}).get("companies", [])
    buyers = network.get("downstream_buyers", {}).get("companies", [])
    evidence = [
        network.get("peer_competitors", {}).get("assessment", ""),
        network.get("downstream_buyers", {}).get("assessment", ""),
        *network.get("monetization_paths", [])[:2],
        *network.get("redeployment_paths", [])[:2],
    ]
    unresolved = package.get("open_questions", [])[:3]
    answer = (
        f"Buyer follow-up for '{question}': "
        f"Peer assessment: {network.get('peer_competitors', {}).get('assessment', 'n/v')}. "
        f"Buyer assessment: {network.get('downstream_buyers', {}).get('assessment', 'n/v')}. "
        f"Visible peer or buyer count: {len(peers)} peers and {len(buyers)} downstream buyers."
    )
    return answer, [item for item in evidence if item], unresolved


def _cross_domain_answer(question: str, pipeline_data: dict[str, Any], run_context: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    synthesis = pipeline_data.get("synthesis", {})
    quality = pipeline_data.get("quality_review", {})
    evidence = [
        synthesis.get("executive_summary", ""),
        synthesis.get("opportunity_assessment_summary", ""),
        *synthesis.get("next_steps", [])[:2],
    ]
    unresolved = quality.get("open_gaps", [])[:3]
    answer = (
        f"Cross-domain follow-up for '{question}': "
        f"{synthesis.get('opportunity_assessment_summary', 'n/v')} "
        f"Recommended next steps: {', '.join(synthesis.get('next_steps', [])[:3]) or 'n/v'}."
    )
    return answer, [item for item in evidence if item], unresolved


def _contact_answer(question: str, pipeline_data: dict[str, Any], run_context: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    section = pipeline_data.get("contact_intelligence", {})
    package = run_context.get("short_term_memory", {}).get("department_packages", {}).get("ContactDepartment", {})
    contacts = section.get("prioritized_contacts", section.get("contacts", []))
    evidence = [
        section.get("narrative_summary", ""),
        *[f"{c.get('name', '')} — {c.get('rolle_titel', '')} at {c.get('firma', '')}" for c in contacts[:3]],
    ]
    unresolved = package.get("open_questions", [])[:3]
    answer = (
        f"Contact intelligence follow-up for '{question}': "
        f"{section.get('narrative_summary', 'n/v')} "
        f"Prioritized contacts found: {len(contacts)}. "
        f"Coverage quality: {section.get('coverage_quality', 'n/v')}."
    )
    return answer, [item for item in evidence if item], unresolved


def _synthesis_answer(question: str, pipeline_data: dict[str, Any], run_context: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    synthesis = pipeline_data.get("synthesis", {})
    package = run_context.get("short_term_memory", {}).get("department_packages", {}).get("SynthesisDepartment", {})
    evidence = [
        synthesis.get("executive_summary", ""),
        synthesis.get("opportunity_assessment_summary", ""),
        package.get("opportunity_assessment", ""),
        *synthesis.get("next_steps", [])[:2],
    ]
    unresolved = synthesis.get("key_risks", [])[:3]
    answer = (
        f"Synthesis follow-up for '{question}': "
        f"{package.get('executive_summary', synthesis.get('executive_summary', 'n/v'))} "
        f"Opportunity: {package.get('opportunity_assessment', synthesis.get('opportunity_assessment_summary', 'n/v'))}."
    )
    return answer, [item for item in evidence if item], unresolved


def answer_follow_up(
    *,
    run_id: str,
    route: str,
    question: str,
    pipeline_data: dict[str, Any],
    run_context: dict[str, Any],
) -> dict[str, Any]:
    if route == "MarketDepartment":
        answer, evidence, unresolved = _market_answer(question, pipeline_data, run_context)
    elif route == "BuyerDepartment":
        answer, evidence, unresolved = _buyer_answer(question, pipeline_data, run_context)
    elif route == "ContactDepartment":
        answer, evidence, unresolved = _contact_answer(question, pipeline_data, run_context)
    elif route in ("SynthesisDepartment", "CrossDomainStrategicAnalyst"):
        answer, evidence, unresolved = _synthesis_answer(question, pipeline_data, run_context)
    else:
        route = "CompanyDepartment"
        answer, evidence, unresolved = _company_answer(question, pipeline_data, run_context)

    payload = FollowUpAnswer(
        run_id=run_id,
        routed_to=route,
        question=question,
        answer=answer,
        evidence_used=evidence[:5],
        unresolved_points=unresolved,
        requires_additional_research=bool(unresolved),
    ).model_dump(mode="json")
    export_follow_up(RUNS_DIR / run_id, payload)
    return payload
