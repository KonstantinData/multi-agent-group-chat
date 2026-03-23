"""Public runner for the supervisor-centric department architecture."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from src.agents.definitions import AGENT_SPECS, create_runtime_agents
from src.config import summarize_worker_report_costs
from src.domain.intake import IntakeRequest
from src.exporters.json_export import export_run
from src.memory.consolidation import consolidate_role_patterns
from src.memory.long_term_store import FileLongTermMemoryStore
from src.memory.policies import should_store_strategy
from src.memory.retrieval import retrieve_strategies
from src.models.registry import assemble_section
from src.models.schemas import empty_pipeline_data, validate_pipeline_data
from src.orchestration.run_context import RunContext
from src.orchestration.supervisor_loop import emit_message, run_supervisor_loop
from src.orchestration.synthesis import (
    assess_research_readiness,
    build_quality_review,
    build_report_package,
    build_synthesis_context,
)
from src.research.normalize import normalize_domain


ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "artifacts" / "runs"
LONG_TERM_MEMORY_PATH = ROOT / "artifacts" / "memory" / "long_term_memory.json"

AGENT_META = {
    name: {"icon": spec.icon, "color": spec.color, "summary": spec.summary}
    for name, spec in AGENT_SPECS.items()
}

PIPELINE_STEPS = [
    ("Supervisor", "Intake + Routing"),
    ("CompanyDepartment", "Company"),
    ("MarketDepartment", "Market"),
    ("BuyerDepartment", "Buyer"),
    ("ContactDepartment", "Contact Intelligence"),
    ("SynthesisDepartment", "Strategic Synthesis"),
    ("ReportWriter", "Report"),
]

MessageHook = Callable[[dict[str, Any]], None] | None


def _timestamp_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _serialize_message_content(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


def _extract_pipeline_data(messages: list[dict[str, Any]]) -> dict[str, Any]:
    pipeline_data = empty_pipeline_data()
    for message in messages:
        content = _serialize_message_content(message)
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        section = payload.get("section")
        if section in {"company_profile", "industry_analysis", "market_network"} and "payload" in payload:
            pipeline_data[section] = payload["payload"]
        if section == "quality_review" and "payload" in payload:
            pipeline_data["quality_review"] = payload["payload"]
        if section == "synthesis" and "payload" in payload:
            pipeline_data["synthesis"] = payload["payload"]
    return validate_pipeline_data(pipeline_data)


def run_pipeline(
    *,
    company_name: str,
    web_domain: str,
    on_message: MessageHook = None,
) -> dict[str, Any]:
    start_time = perf_counter()
    run_id = _timestamp_run_id()
    run_dir = RUNS_DIR / run_id
    intake = IntakeRequest(company_name=company_name, web_domain=web_domain)
    agents = create_runtime_agents()

    memory_store = FileLongTermMemoryStore(LONG_TERM_MEMORY_PATH)
    run_context = RunContext(
        run_id=run_id,
        intake={"company_name": company_name, "web_domain": web_domain, "language": intake.language},
    )
    run_context.retrieved_strategies = retrieve_strategies(
        memory_store,
        domain=normalize_domain(web_domain),
        limit=5,
    )
    run_context.retrieved_role_strategies = {
        role: retrieve_strategies(
            memory_store,
            domain=normalize_domain(web_domain),
            role=role,
            limit=3,
        )
        for role in [
            "Supervisor",
            "CompanyLead",
            "CompanyResearcher",
            "CompanyCritic",
            "MarketLead",
            "MarketResearcher",
            "MarketCritic",
            "BuyerLead",
            "BuyerResearcher",
            "BuyerCritic",
            "CrossDomainStrategicAnalyst",
            "ReportWriter",
        ]
    }

    messages: list[dict[str, Any]] = []
    try:
        brief, supervisor_message = agents["supervisor"].build_intake_brief(intake)
        run_context.supervisor_brief = supervisor_message["payload"]
        messages.append(
            emit_message(
                on_message,
                agent="Supervisor",
                content=json.dumps(supervisor_message, ensure_ascii=False),
            )
        )

        sections, department_packages, loop_messages, completed_backlog, department_timings = run_supervisor_loop(
            brief=brief,
            run_context=run_context,
            agents=agents,
            on_message=on_message,
        )
        messages.extend(loop_messages)
        run_context.short_term_memory.task_statuses.update(
            {item["task_key"]: item["status"] for item in completed_backlog}
        )

        # Quality review still derived from memory snapshot
        quality_review = build_quality_review(run_context.short_term_memory.snapshot())
        messages.append(
            emit_message(
                on_message,
                agent="SynthesisDepartment",
                content=json.dumps({"section": "quality_review", "payload": quality_review}, ensure_ascii=False),
            )
        )

        # Single authoritative synthesis path — AG2 SynthesisDepartment is the author.
        # build_synthesis_context() prepares a fallback payload only; it is used when
        # AG2 did not complete (generation_mode="fallback").  Confidence is derived
        # from input package quality, not from the generation mode.
        ag2_synthesis = sections.get("synthesis")
        if ag2_synthesis and ag2_synthesis.get("target_company", "n/v") != "n/v":
            evidence_health = quality_review.get("evidence_health", "low")
            synthesis = {
                **ag2_synthesis,
                "generation_mode": "normal",
                "confidence": evidence_health,
            }
        else:
            synthesis_ctx = build_synthesis_context(
                company_profile=sections.get("company_profile", {}),
                industry_analysis=sections.get("industry_analysis", {}),
                market_network=sections.get("market_network", {}),
                contact_intelligence=sections.get("contact_intelligence", {}),
                quality_review=quality_review,
                memory_snapshot=run_context.short_term_memory.snapshot(),
            )
            synthesis = {**synthesis_ctx, "generation_mode": "fallback"}

        readiness = assess_research_readiness(
            company_profile=sections.get("company_profile", {}),
            industry_analysis=sections.get("industry_analysis", {}),
            market_network=sections.get("market_network", {}),
            contact_intelligence=sections.get("contact_intelligence", {}),
            quality_review=quality_review,
        )
        pipeline_data = validate_pipeline_data(
            {
                "company_profile": assemble_section("company_profile", sections.get("company_profile", {})),
                "industry_analysis": assemble_section("industry_analysis", sections.get("industry_analysis", {})),
                "market_network": assemble_section("market_network", sections.get("market_network", {})),
                "contact_intelligence": assemble_section("contact_intelligence", sections.get("contact_intelligence", {})),
                "quality_review": quality_review,
                "synthesis": synthesis,
                "research_readiness": readiness,
                "validation_errors": [],
            }
        )

        report_package = build_report_package(
            pipeline_data=pipeline_data,
            department_packages=department_packages,
        )
        run_context.report_package = report_package
        messages.append(
            emit_message(
                on_message,
                agent="ReportWriter",
                content=json.dumps({"section": "report_package", "payload": report_package}, ensure_ascii=False),
            )
        )

        if readiness["usable"]:
            status = "completed"
        elif readiness.get("partial"):
            status = "completed_partial"
        else:
            status = "completed_but_not_usable"
        run_context.status = status
        elapsed_seconds = round(perf_counter() - start_time, 3)
        memory_snapshot = run_context.short_term_memory.snapshot()
        usage = summarize_worker_report_costs(memory_snapshot.get("worker_reports", []))
        usage_total = usage.get("total", {})
        usage_totals = memory_snapshot.get("usage_totals", {})
        budget = {
            "total_pipeline_events": len(messages),
            "tool_calls_used": int(
                (usage_totals.get("search_calls", 0) or 0)
                + (usage_totals.get("page_fetches", 0) or 0)
                + (usage_totals.get("llm_calls", 0) or 0)
            ),
            "max_tool_calls": 140,
            "max_department_attempts": 3,
            "llm_calls_used": int(usage_totals.get("llm_calls", 0) or 0),
            "search_calls_used": int(usage_totals.get("search_calls", 0) or 0),
            "page_fetches_used": int(usage_totals.get("page_fetches", 0) or 0),
            "estimated_cost_usd": float(usage_total.get("total_cost", 0.0) or 0.0),
            "elapsed_seconds": elapsed_seconds,
            "department_timings": department_timings,
        }
        run_context_snapshot = run_context.snapshot()

        role_patterns = consolidate_role_patterns(
            run_context=run_context_snapshot,
            pipeline_data=pipeline_data,
            status=status,
            usable=readiness["usable"],
        )
        if role_patterns and should_store_strategy(status=status, usable=readiness["usable"]):
            for pattern in role_patterns:
                memory_store.upsert_strategy(pattern)

        export_run(
            run_dir=run_dir,
            run_id=run_id,
            company_name=company_name,
            web_domain=web_domain,
            status=status,
            messages=messages,
            pipeline_data=pipeline_data,
            run_context=run_context_snapshot,
            usage=usage,
            budget=budget,
        )
        return {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "messages": messages,
            "pipeline_data": pipeline_data,
            "run_context": run_context_snapshot,
            "usage": usage,
            "budget": budget,
            "status": status,
            "error": None,
        }
    except Exception as exc:
        error_message = str(exc)
        run_context.status = "failed"
        elapsed_seconds = round(perf_counter() - start_time, 3)
        export_run(
            run_dir=run_dir,
            run_id=run_id,
            company_name=company_name,
            web_domain=web_domain,
            status="failed",
            messages=messages,
            pipeline_data=empty_pipeline_data(),
            run_context=run_context.snapshot(),
            budget={"elapsed_seconds": elapsed_seconds},
            error=error_message,
        )
        return {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "messages": messages,
            "pipeline_data": empty_pipeline_data(),
            "run_context": run_context.snapshot(),
            "usage": {},
            "budget": {"elapsed_seconds": elapsed_seconds},
            "status": "failed",
            "error": error_message,
        }
