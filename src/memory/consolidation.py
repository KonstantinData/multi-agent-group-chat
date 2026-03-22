"""Convert finished runs into reusable role-specific strategy patterns."""
from __future__ import annotations

from typing import Any


def consolidate_role_patterns(
    *,
    run_context: dict[str, Any],
    pipeline_data: dict[str, Any],
    status: str,
    usable: bool,
) -> list[dict[str, Any]]:
    if status != "completed" or not usable:
        return []

    brief = run_context.get("supervisor_brief", {})
    short_term_memory = run_context.get("short_term_memory", {})
    retrieved = run_context.get("retrieved_strategies", [])
    domain = brief.get("normalized_domain", "")
    industry_hint = pipeline_data.get("company_profile", {}).get("industry", "n/v")
    useful_source_types = sorted(
        {
            source.get("source_type", "secondary")
            for source in short_term_memory.get("sources", [])
            if isinstance(source, dict)
        }
    )
    patterns: list[dict[str, Any]] = []
    worker_reports = short_term_memory.get("worker_reports", [])

    grouped_queries: dict[str, list[str]] = {}
    for report in worker_reports:
        grouped_queries.setdefault(str(report.get("worker", "worker")), []).extend(report.get("queries_used", []))

    patterns.append(
        {
            "name": f"{domain}-supervisor-strategy",
            "role": "Supervisor",
            "pattern_scope": "orchestration",
            "domain": domain,
            "industry_hint": industry_hint,
            "successful_queries": list(dict.fromkeys(query for values in grouped_queries.values() for query in values)),
            "useful_source_types": useful_source_types,
            "rationale": (
                f"Supervisor run completed with {len(worker_reports)} worker reports "
                f"and {len(retrieved)} retrieved prior strategies."
            ),
            "score": 1.0,
        }
    )

    for role_name, queries in grouped_queries.items():
        patterns.append(
            {
                "name": f"{domain}-{role_name.lower()}-strategy",
                "role": role_name,
                "pattern_scope": "worker_strategy",
                "domain": domain,
                "industry_hint": industry_hint,
                "successful_queries": list(dict.fromkeys(queries)),
                "useful_source_types": useful_source_types,
                "rationale": f"{role_name} completed accepted work with reusable query paths.",
                "score": 1.0,
            }
        )

    critic_reviews = short_term_memory.get("critic_reviews", {})
    if critic_reviews:
        for critic_role in ["CompanyCritic", "MarketCritic", "BuyerCritic", "ContactCritic", "SynthesisCritic"]:
            dept_prefix = critic_role.replace("Critic", "").lower()
            dept_reviews = {k: v for k, v in critic_reviews.items() if dept_prefix in k.lower()}
            if not dept_reviews:
                continue
            patterns.append(
                {
                    "name": f"{domain}-{dept_prefix}-critic-strategy",
                    "role": critic_role,
                    "pattern_scope": "review_strategy",
                    "domain": domain,
                    "industry_hint": industry_hint,
                    "successful_queries": [],
                    "useful_source_types": useful_source_types,
                    "rationale": f"{critic_role} review patterns for reusable quality thresholds.",
                    "score": 1.0,
                    "accepted_points": {k: v for k, v in short_term_memory.get("accepted_points", {}).items() if dept_prefix in k.lower()},
                    "open_points": {k: v for k, v in short_term_memory.get("open_points", {}).items() if dept_prefix in k.lower()},
                }
            )

    # Contact Intelligence pattern
    contact_workspace = short_term_memory.get("department_workspaces", {}).get("ContactDepartment", {})
    if contact_workspace.get("worker_reports"):
        contact_queries = list(dict.fromkeys(
            q for r in contact_workspace["worker_reports"] for q in r.get("queries_used", [])
        ))
        patterns.append(
            {
                "name": f"{domain}-contact-intelligence-strategy",
                "role": "ContactResearcher",
                "pattern_scope": "contact_strategy",
                "domain": domain,
                "industry_hint": industry_hint,
                "successful_queries": contact_queries,
                "useful_source_types": useful_source_types,
                "rationale": "Contact discovery queries that identified decision-makers at buyer firms.",
                "score": 1.0,
            }
        )

    return patterns
