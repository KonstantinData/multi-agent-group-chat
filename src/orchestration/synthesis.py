"""Cross-domain synthesis and report shaping."""
from __future__ import annotations

from typing import Any


NEGATIVE_PREFIXES = ("no ", "not ", "none", "kein", "keine", "keinen")


def _positive_signals(items: list[str]) -> list[str]:
    positives: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered.startswith(NEGATIVE_PREFIXES):
            continue
        positives.append(text)
    return positives


def build_quality_review(memory_snapshot: dict[str, Any]) -> dict[str, Any]:
    approvals = memory_snapshot.get("critic_approvals", {})
    approved_tasks = [task_key for task_key, approved in approvals.items() if approved]
    task_statuses = memory_snapshot.get("task_statuses", {})
    accepted_backlog = [task_key for task_key, status in task_statuses.items() if status == "accepted"]
    sources = memory_snapshot.get("sources", [])
    open_questions = memory_snapshot.get("open_questions", [])
    external_sources = [
        source for source in sources if isinstance(source, dict) and source.get("source_type") not in {"owned", "first_party"}
    ]
    open_points = memory_snapshot.get("open_points", {})
    unresolved_points = sorted({point for points in open_points.values() for point in points})
    evidence_health = "low"
    if len(accepted_backlog) >= 8 and len(external_sources) >= 2 and not unresolved_points:
        evidence_health = "high"
    elif len(accepted_backlog) >= 6 and len(external_sources) >= 1:
        evidence_health = "medium"
    return {
        "validated_agents": ["Supervisor", "CompanyDepartment", "MarketDepartment", "BuyerDepartment", *sorted(approved_tasks)],
        "evidence_health": evidence_health,
        "open_gaps": list(dict.fromkeys([*open_questions, *unresolved_points])),
        "recommendations": [
            "Validate likely buyers against CRM before the meeting.",
            "Confirm economic pressure signals with fresher external evidence where possible.",
        ],
        "gap_details": [
            {
                "agent": "Supervisor",
                "field_path": "*",
                "issue_type": "open_question",
                "severity": "moderate",
                "summary": question,
                "recommendation": "Use follow-up mode or customer discovery to close this gap.",
            }
            for question in list(dict.fromkeys(open_questions))[:5]
        ],
    }


def _service_relevance(industry: dict[str, Any], market: dict[str, Any]) -> list[dict[str, str]]:
    monetization = _positive_signals(market.get("monetization_paths", []))
    redeployment = _positive_signals(market.get("redeployment_paths", []))
    analytics = _positive_signals(industry.get("analytics_signals", []))
    downstream_buyers = market.get("downstream_buyers", {}).get("companies", [])

    items: list[dict[str, str]] = []
    items.append(
        {
            "service_area": "excess_inventory",
            "relevance": "medium" if monetization and downstream_buyers else "unclear",
            "reasoning": (
                "Indicative resale or buyer routes were identified with at least one buyer signal."
                if monetization and downstream_buyers
                else "No validated monetization route with buyer evidence is available yet."
            ),
        }
    )
    items.append(
        {
            "service_area": "repurposing",
            "relevance": "medium" if redeployment else "unclear",
            "reasoning": (
                "At least one redeployment or repurposing hypothesis exists."
                if redeployment
                else "No validated repurposing path is available yet."
            ),
        }
    )
    items.append(
        {
            "service_area": "analytics",
            "relevance": "medium" if analytics else "unclear",
            "reasoning": (
                "Operational visibility or decision-support leverage is indicated."
                if analytics
                else "No concrete analytics pain point is available yet."
            ),
        }
    )
    return items


def build_synthesis_context(
    *,
    company_profile: dict[str, Any],
    industry_analysis: dict[str, Any],
    market_network: dict[str, Any],
    quality_review: dict[str, Any],
    memory_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Prepare a synthesis context payload from department outputs.

    This is pre-processing input for the AG2 SynthesisDepartment, not a
    parallel synthesis author.  When AG2 succeeds, the AG2 output takes
    authority (generation_mode="normal").  When AG2 times out or fails,
    this context is promoted to the final synthesis with
    generation_mode="fallback".  Confidence is derived from input package
    quality — fallback does NOT automatically mean low confidence.
    """
    service_relevance = _service_relevance(industry_analysis, market_network)
    if quality_review.get("evidence_health") == "low":
        service_relevance = [
            {
                **item,
                "relevance": "unclear",
                "reasoning": "Evidence quality is too weak for a confident service recommendation.",
            }
            for item in service_relevance
        ]
    positive_service_areas = [item["service_area"] for item in service_relevance if item["relevance"] != "unclear"]
    recommended_paths = positive_service_areas or ["further_validation_required"]

    peer_competitors = market_network.get("peer_competitors", {}).get("companies", [])
    downstream_buyers = market_network.get("downstream_buyers", {}).get("companies", [])
    service_providers = market_network.get("service_providers", {}).get("companies", [])
    cross_industry_buyers = market_network.get("cross_industry_buyers", {}).get("companies", [])

    case_assessments = [
        {
            "option": item["service_area"],
            "arguments": [
                {
                    "argument": item["reasoning"],
                    "direction": "pro" if item["relevance"] != "unclear" else "contra",
                    "based_on": "validated_department_packages",
                }
            ],
            "summary": item["reasoning"],
        }
        for item in service_relevance
    ]

    _OPEN_QUESTION_STARTERS = (
        "what ", "how ", "who ", "when ", "where ", "why ", "which ",
        "are there", "is there", "does ", "do ", "can ",
    )

    def _is_genuine_risk(text: str) -> bool:
        t = text.strip()
        if not t:
            return False
        if t.startswith("Point '"):               # critic internal: "Point 'field' is still insufficient..."
            return False
        if " " not in t:                           # bare field names like "buyer_or_path_signal"
            return False
        if t.lower().startswith("no supporting source"):
            return False
        tl = t.lower()
        if any(tl.startswith(s) for s in _OPEN_QUESTION_STARTERS):  # open questions belong in next_steps
            return False
        if tl.startswith("no verified") or tl.startswith("no external search") or tl.startswith("supporting page excerpts"):
            return False
        return True

    _filtered_risks = [r for r in dict.fromkeys(quality_review.get("open_gaps", [])) if _is_genuine_risk(r)]
    if _filtered_risks:
        key_risks = _filtered_risks
    elif quality_review.get("evidence_health") in {"high", "medium"}:
        # Good run — name the real gaps that remain
        _fallback_risks: list[str] = []
        if not market_network.get("peer_competitors", {}).get("companies"):
            _fallback_risks.append("Competitive landscape not yet verified — confirm peer positioning before the meeting.")
        if not downstream_buyers:
            _fallback_risks.append("Downstream buyer list is indicative only — validate against CRM.")
        if not market_network.get("cross_industry_buyers", {}).get("companies"):
            _fallback_risks.append("Cross-industry buyer paths not identified — may limit resale scope.")
        contact_intel = memory_snapshot.get("contact_intelligence", {})
        if not (contact_intel.get("verified_contacts") or contact_intel.get("buyer_contacts")):
            _fallback_risks.append("No verified decision-maker contacts found — identify procurement lead before outreach.")
        key_risks = _fallback_risks or ["Evidence base is solid; validate contacts and financials directly in the meeting."]
    else:
        key_risks = ["Public web evidence remains incomplete and should be validated in the meeting."]
    next_steps = list(dict.fromkeys(memory_snapshot.get("next_actions", []))) or [
        "Validate buyer paths and inventory pressure directly with the prospect."
    ]

    return {
        "target_company": company_profile.get("company_name", "n/v"),
        "executive_summary": (
            f"{company_profile.get('company_name', 'The target company')} appears to operate in "
            f"{company_profile.get('industry', 'an unclear industry')}. "
            "The briefing is based on approved company, market, and buyer department packages."
        ),
        "liquisto_service_relevance": service_relevance,
        "opportunity_assessment_summary": (
            "The most plausible Liquisto path was derived after cross-domain review of the approved department packages."
        ),
        "recommended_engagement_paths": recommended_paths,
        "case_assessments": case_assessments,
        "buyer_market_summary": market_network.get("downstream_buyers", {}).get("assessment", "n/v"),
        "total_peer_competitors": len(peer_competitors),
        "total_downstream_buyers": len(downstream_buyers),
        "total_service_providers": len(service_providers),
        "total_cross_industry_buyers": len(cross_industry_buyers),
        "key_risks": key_risks,
        "next_steps": next_steps,
        "sources": memory_snapshot.get("sources", []),
        # Confidence derived from input package quality (orthogonal to generation_mode)
        "confidence": quality_review.get("evidence_health", "low"),
    }


def build_report_package(
    *,
    pipeline_data: dict[str, Any],
    department_packages: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    synthesis = pipeline_data.get("synthesis", {})
    company = pipeline_data.get("company_profile", {})
    quality = pipeline_data.get("quality_review", {})
    return {
        "report_status": "ready",
        "report_title": f"Liquisto Briefing - {company.get('company_name', 'n/v')}",
        "executive_summary": synthesis.get("executive_summary", "n/v"),
        "department_visual_focus": {
            name: package.get("visual_focus", [])
            for name, package in department_packages.items()
        },
        "recommended_sections": [
            "Executive summary",
            "Company snapshot",
            "Market and operational signals",
            "Buyer and redeployment paths",
            "Liquisto opportunity assessment",
            "Negotiation relevance and next steps",
            "Evidence appendix",
        ],
        "open_gaps": quality.get("open_gaps", []),
    }


def assess_research_readiness(
    *,
    company_profile: dict[str, Any],
    industry_analysis: dict[str, Any],
    market_network: dict[str, Any],
    quality_review: dict[str, Any],
) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    if company_profile.get("company_name") != "n/v":
        score += 35
    else:
        reasons.append("Company profile is still incomplete.")
    if industry_analysis.get("industry_name") != "n/v":
        score += 25
    else:
        reasons.append("Industry analysis is incomplete.")
    if market_network.get("target_company") != "n/v":
        score += 20
    else:
        reasons.append("Buyer landscape is incomplete.")
    if quality_review.get("evidence_health") == "high":
        score += 20
    elif quality_review.get("evidence_health") == "medium":
        score += 10
        reasons.append("Evidence quality is only moderate and should be strengthened before the meeting.")
    else:
        reasons.append("Evidence quality is too weak for a confident meeting brief.")
    if quality_review.get("open_gaps"):
        reasons.append("Open critic gaps remain unresolved.")
    usable = score >= 70 and quality_review.get("evidence_health") in {"high", "medium"}
    return {"usable": usable, "score": score, "reasons": reasons}
