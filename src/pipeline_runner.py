"""Pipeline runner with callback support for live UI updates."""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import traceback
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic, sleep
from typing import Any, Callable

from pydantic import ValidationError

from src.models.schemas import (
    CompanyProfile,
    IndustryAnalysis,
    MarketNetwork,
    QualityReview,
    SynthesisReport,
)
from src.exporters.json_export import export_run

# --- Logging setup ---
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")

# Agent display metadata
AGENT_META = {
    "Admin":                {"icon": "👤", "color": "#6c757d"},
    "Concierge":            {"icon": "🛎️", "color": "#0d6efd"},
    "ConciergeCritic":      {"icon": "🧪", "color": "#6f42c1"},
    "CompanyIntelligence":  {"icon": "🏢", "color": "#198754"},
    "CompanyIntelligenceCritic": {"icon": "🧪", "color": "#146c43"},
    "StrategicSignals":     {"icon": "📡", "color": "#6610f2"},
    "StrategicSignalsCritic": {"icon": "🧪", "color": "#7c3aed"},
    "MarketNetwork":        {"icon": "🌐", "color": "#fd7e14"},
    "MarketNetworkCritic":  {"icon": "🧪", "color": "#b45309"},
    "EvidenceQA":           {"icon": "🔍", "color": "#dc3545"},
    "EvidenceQACritic":     {"icon": "🧪", "color": "#991b1b"},
    "Synthesis":            {"icon": "📋", "color": "#20c997"},
    "SynthesisCritic":      {"icon": "🧪", "color": "#0f766e"},
    "chat_manager":         {"icon": "⚙️", "color": "#adb5bd"},
}

PIPELINE_STEPS = [
    ("Concierge", "Intake validieren"),
    ("CompanyIntelligence", "Firmenprofil erstellen"),
    ("StrategicSignals", "Branchenanalyse"),
    ("MarketNetwork", "Käufernetzwerk ermitteln"),
    ("EvidenceQA", "Evidenz prüfen"),
    ("Synthesis", "Briefing erstellen"),
]

COMPANY_SOURCE_MAX_AGE_DAYS = 730
INDUSTRY_SOURCE_MAX_AGE_DAYS = 540
BUYER_SOURCE_MAX_AGE_DAYS = 730
MAX_STAGE_ATTEMPTS = int(os.environ.get("PIPELINE_MAX_STAGE_ATTEMPTS", "3"))
MAX_TOOL_CALLS = int(os.environ.get("PIPELINE_MAX_TOOL_CALLS", "24"))
MAX_RUN_SECONDS = int(os.environ.get("PIPELINE_MAX_RUN_SECONDS", "600"))
MAX_GROUPCHAT_ROUNDS = 1 + (len(PIPELINE_STEPS) * MAX_STAGE_ATTEMPTS * 2) + 2
GROUPCHAT_POLL_INTERVAL_SECONDS = 0.2
GROUPCHAT_STOP_GRACE_SECONDS = 5.0
PREPARE_GROUP_CHAT_RESULT_LEN = 13


@dataclass
class PreparedGroupChat:
    context_variables: Any
    groupchat: Any
    manager: Any
    processed_messages: list[dict[str, Any]]
    last_agent: Any


def build_pipeline_task(company_name: str, web_domain: str) -> str:
    """Build the shared end-to-end task prompt for the AutoGen pipeline."""
    return (
        f"Research the company '{company_name}' (domain: {web_domain}) "
        f"for a Liquisto sales meeting preparation.\n\n"
        f"Run the full pipeline:\n"
        f"1. Concierge: Validate intake and build research brief\n"
        f"2. CompanyIntelligence: Build comprehensive company profile\n"
        f"3. StrategicSignals: Analyze industry trends and overcapacity signals\n"
        f"4. MarketNetwork: Identify buyers across 4 tiers "
        f"(Peer Competitors, Downstream Buyers, Service Providers, Cross-Industry)\n"
        f"5. EvidenceQA: Review evidence quality and flag gaps\n"
        f"6. Synthesis: Compile final briefing with pro/contra arguments "
        f"for Kaufen/Kommission/Ablehnen and Liquisto service area relevance\n\n"
        f"Each agent MUST output structured JSON matching the defined schemas. "
        f"Do not output anything else besides the JSON."
    )


def run_pipeline(
    company_name: str,
    web_domain: str,
    on_message: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the full pipeline. Calls on_message(event) for each agent message."""
    from src.config import get_llm_config
    from src.agents.definitions import create_agents, create_group_pattern

    def _emit(event_type: str, agent: str, content: str):
        event = {
            "type": event_type,
            "agent": agent,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "meta": AGENT_META.get(agent, {"icon": "⚙️", "color": "#adb5bd"}),
        }
        collected_messages.append(event)
        if on_message:
            on_message(event)

    collected_messages: list[dict[str, Any]] = []
    chat_history: list[dict[str, Any]] = []
    budget_state = _build_budget_state()

    log.info("=" * 60)
    log.info("PIPELINE START: %s (%s)", company_name, web_domain)
    log.info("=" * 60)
    _emit("debug", "System", f"Pipeline gestartet für: {company_name} ({web_domain})")

    try:
        log.debug("Loading LLM config...")
        llm_config = get_llm_config()
        model = llm_config.config_list[0].model
        log.info("LLM config loaded: model=%s", model)
        _emit("debug", "System", f"LLM Model: {model}")
    except Exception as e:
        log.error("Failed to load LLM config: %s", e)
        _emit("error", "System", f"LLM Config Fehler: {e}")
        raise

    try:
        log.debug("Creating agents...")
        agents = create_agents(llm_config)
        log.info("Agents created: %s", list(agents.keys()))
        _emit("debug", "System", f"Agenten erstellt: {', '.join(agents.keys())}")
    except Exception as e:
        log.error("Failed to create agents: %s", e)
        _emit("error", "System", f"Agent-Erstellung fehlgeschlagen: {e}")
        raise

    try:
        log.debug("Creating AG2 workflow pattern...")
        pattern = create_group_pattern(agents, llm_config)
        prepared_chat = _prepare_group_chat(
            pattern,
            max_rounds=budget_state["max_groupchat_rounds"],
            messages=build_pipeline_task(company_name, web_domain),
        )
        log.info("AG2 pattern created: max_round=%s", prepared_chat.groupchat.max_round)
        _emit("debug", "System", f"AG2 Pattern erstellt: max_round={prepared_chat.groupchat.max_round}")
    except Exception as e:
        log.error("Failed to create AG2 workflow pattern: %s", e)
        _emit("error", "System", f"AG2 Pattern Fehler: {e}")
        raise

    task = (
        prepared_chat.processed_messages[-1]["content"]
        if prepared_chat.processed_messages
        else build_pipeline_task(company_name, web_domain)
    )
    log.info("Task built (%d chars)", len(task))
    _emit("debug", "System", "Task erstellt, starte AG2 Handoff-Workflow...")
    _emit(
        "debug",
        "System",
        (
            "Budget aktiv: "
            f"{budget_state['max_groupchat_rounds']} GroupChat-Runden, "
            f"{budget_state['max_stage_attempts']} Versuche je Producer/Critic-Stufe, "
            f"{budget_state['max_tool_calls']} Tool-Calls, "
            f"{budget_state['max_run_seconds']}s Laufzeit."
        ),
    )

    try:
        chat_result_holder: dict[str, Any] = {}
        chat_error_holder: dict[str, BaseException] = {}
        sender, initial_message, clear_history = _resolve_group_chat_entrypoint(prepared_chat, fallback_message=task)

        def _run_groupchat() -> None:
            try:
                chat_result_holder["result"] = sender.initiate_chat(
                    prepared_chat.manager,
                    message=initial_message,
                    clear_history=clear_history,
                    summary_method=pattern.summary_method,
                    silent=True,
                )
            except BaseException as exc:
                chat_error_holder["error"] = exc

        worker = threading.Thread(target=_run_groupchat, daemon=True)
        worker.start()
        emitted_count = 0
        timed_out = False
        while worker.is_alive():
            emitted_count = _emit_groupchat_messages(prepared_chat.groupchat.messages, emitted_count, _emit)
            if _run_budget_exceeded(budget_state):
                timed_out = True
                _request_group_chat_stop(prepared_chat, sender)
                _emit(
                    "error",
                    "System",
                    (
                        "Laufzeitbudget überschritten "
                        f"({budget_state['max_run_seconds']}s). Stoppe den Workflow nach dem aktuellen AG2-Zug."
                    ),
                )
                break
            sleep(GROUPCHAT_POLL_INTERVAL_SECONDS)

        if timed_out:
            worker.join(timeout=GROUPCHAT_STOP_GRACE_SECONDS)
            emitted_count = _emit_groupchat_messages(prepared_chat.groupchat.messages, emitted_count, _emit)
            if worker.is_alive():
                raise TimeoutError(
                    "Pipeline exceeded the configured runtime budget and did not stop cleanly."
                )
            raise TimeoutError("Pipeline exceeded the configured runtime budget.")

        worker.join()
        emitted_count = _emit_groupchat_messages(prepared_chat.groupchat.messages, emitted_count, _emit)

        if "error" in chat_error_holder:
            raise chat_error_holder["error"]

        chat_result = chat_result_holder.get("result")
        chat_history = list(getattr(chat_result, "chat_history", None) or prepared_chat.groupchat.messages)
        log.info("AG2 workflow completed with %d chat messages", len(chat_history))
        _emit("debug", "System", f"Chat beendet. {len(chat_history)} Nachrichten.")
    except Exception as e:
        log.error("AG2 workflow FAILED: %s\n%s", e, traceback.format_exc())
        _emit("error", "System", f"Chat-Fehler: {e}")
        raise

    result = {"chat_history": chat_history}
    pipeline_messages = _normalize_chat_history(result)
    pipeline_data = _extract_pipeline_data(pipeline_messages)
    usage_summary = _collect_usage_summary(agents)
    filled = [k for k, v in pipeline_data.items() if k != "validation_errors" and v]
    log.info("Parsed pipeline data. Filled keys: %s", filled)
    _emit("debug", "System", f"Ergebnisse geparst: {', '.join(filled) or 'keine'}")
    if usage_summary["total"].get("total_cost"):
        _emit(
            "debug",
            "System",
            (
                "Usage erfasst: "
                f"${usage_summary['total']['total_cost']:.4f}, "
                f"{usage_summary['total'].get('prompt_tokens', 0)} Prompt-Tokens, "
                f"{usage_summary['total'].get('completion_tokens', 0)} Completion-Tokens."
            ),
        )

    validation_errors = pipeline_data.get("validation_errors", [])
    if validation_errors:
        for error in validation_errors:
            agent = error.get("agent", "unknown")
            section = error.get("section", "unknown")
            details = error.get("details", "Schema validation failed")
            log.warning("Validation failed for %s/%s: %s", agent, section, details)
            _emit("error", "System", f"Schema-Validierung fehlgeschlagen ({agent}/{section}): {details}")

    # --- Step 8: Export ---
    try:
        run_id = uuid.uuid4().hex[:12]
        run_dir = export_run(
            run_id,
            result,
            pipeline_data=pipeline_data,
            run_meta_extra={
                "usage": usage_summary,
                "budget": {
                    "max_groupchat_rounds": budget_state["max_groupchat_rounds"],
                    "max_stage_attempts": budget_state["max_stage_attempts"],
                    "max_tool_calls": budget_state["max_tool_calls"],
                    "tool_calls_used": int(prepared_chat.context_variables.get("tool_calls_used", 0) or 0),
                    "groupchat_rounds_used": len(chat_history),
                    "max_run_seconds": budget_state["max_run_seconds"],
                    "elapsed_seconds": round(monotonic() - budget_state["started_at"], 3),
                },
            },
        )
        log.info("Exported to: %s", run_dir)
        _emit("debug", "System", f"Export: {run_dir}")
    except Exception as e:
        log.error("Export failed: %s", e)
        run_id = "export_failed"
        run_dir = ""

    log.info("=" * 60)
    log.info("PIPELINE DONE: run_id=%s, messages=%d", run_id, len(collected_messages))
    log.info("=" * 60)

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "messages": collected_messages,
        "pipeline_data": pipeline_data,
        "usage": usage_summary,
        "budget": {
            "max_groupchat_rounds": budget_state["max_groupchat_rounds"],
            "max_stage_attempts": budget_state["max_stage_attempts"],
            "max_tool_calls": budget_state["max_tool_calls"],
            "tool_calls_used": int(prepared_chat.context_variables.get("tool_calls_used", 0) or 0),
            "groupchat_rounds_used": len(chat_history),
            "max_run_seconds": budget_state["max_run_seconds"],
            "elapsed_seconds": round(monotonic() - budget_state["started_at"], 3),
        },
    }


def _prepare_group_chat(pattern: Any, max_rounds: int, messages: list[dict[str, Any]] | str) -> PreparedGroupChat:
    prepared = pattern.prepare_group_chat(max_rounds=max_rounds, messages=messages)
    if not isinstance(prepared, tuple) or len(prepared) != PREPARE_GROUP_CHAT_RESULT_LEN:
        raise RuntimeError(
            "Unexpected AG2 prepare_group_chat result shape. Review the installed autogen/ag2 version."
        )

    return PreparedGroupChat(
        context_variables=prepared[3],
        groupchat=prepared[7],
        manager=prepared[8],
        processed_messages=list(prepared[9]),
        last_agent=prepared[10],
    )


def _resolve_group_chat_entrypoint(
    prepared_chat: PreparedGroupChat,
    fallback_message: str,
) -> tuple[Any, dict[str, Any] | str, bool]:
    clear_history = len(prepared_chat.processed_messages) <= 1

    if len(prepared_chat.processed_messages) > 1:
        sender, initial_message = prepared_chat.manager.resume(
            messages=prepared_chat.processed_messages,
            silent=True,
        )
        if sender is None:
            raise ValueError("AG2 pattern did not select an initial agent.")
        return sender, initial_message, clear_history

    if prepared_chat.last_agent is None:
        raise ValueError("AG2 pattern did not prepare an initial speaker.")

    initial_message = prepared_chat.processed_messages[0] if prepared_chat.processed_messages else fallback_message
    return prepared_chat.last_agent, initial_message, clear_history


def _run_budget_exceeded(budget_state: dict[str, Any]) -> bool:
    max_run_seconds = int(budget_state.get("max_run_seconds", 0) or 0)
    if max_run_seconds <= 0:
        return False
    return (monotonic() - budget_state["started_at"]) >= max_run_seconds


def _request_group_chat_stop(prepared_chat: PreparedGroupChat, sender: Any) -> None:
    for participant in getattr(prepared_chat.groupchat, "agents", []):
        if hasattr(participant, "stop_reply_at_receive"):
            participant.stop_reply_at_receive()
    if hasattr(prepared_chat.manager, "stop_reply_at_receive"):
        prepared_chat.manager.stop_reply_at_receive(sender)
        prepared_chat.manager.stop_reply_at_receive()
    if hasattr(sender, "stop_reply_at_receive"):
        sender.stop_reply_at_receive()
    if hasattr(prepared_chat.groupchat, "max_round"):
        prepared_chat.groupchat.max_round = min(
            int(prepared_chat.groupchat.max_round),
            max(len(getattr(prepared_chat.groupchat, "messages", [])), 1),
        )

def _build_budget_state() -> dict[str, Any]:
    return {
        "started_at": monotonic(),
        "max_groupchat_rounds": MAX_GROUPCHAT_ROUNDS,
        "max_stage_attempts": MAX_STAGE_ATTEMPTS,
        "max_tool_calls": MAX_TOOL_CALLS,
        "max_run_seconds": MAX_RUN_SECONDS,
    }


def _emit_groupchat_messages(
    messages: list[dict[str, Any]],
    emitted_count: int,
    emit: Callable[[str, str, str], None],
) -> int:
    for msg in messages[emitted_count:]:
        agent = msg.get("name", msg.get("role", "unknown"))
        content = msg.get("content", "") or ""
        emit("agent_message", agent, str(content))
        emitted_count += 1
    return emitted_count


def _collect_usage_summary(agents: dict[str, Any]) -> dict[str, Any]:
    per_agent: dict[str, Any] = {}
    total_actual = _empty_usage_totals()
    total_total = _empty_usage_totals()

    for agent_name, agent in agents.items():
        actual = _normalize_usage_summary(agent.get_actual_usage() if hasattr(agent, "get_actual_usage") else None)
        total = _normalize_usage_summary(agent.get_total_usage() if hasattr(agent, "get_total_usage") else None)
        if actual["total_cost"] or actual["models"]:
            per_agent[agent_name] = {
                "actual": actual,
                "total": total,
            }
        total_actual = _merge_usage_totals(total_actual, actual)
        total_total = _merge_usage_totals(total_total, total)

    return {
        "actual": total_actual,
        "total": total_total,
        "agents": per_agent,
    }


def _empty_usage_totals() -> dict[str, Any]:
    return {
        "total_cost": 0.0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "models": {},
    }


def _normalize_usage_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    normalized = _empty_usage_totals()
    if not summary:
        return normalized

    normalized["total_cost"] = round(float(summary.get("total_cost", 0.0) or 0.0), 8)
    for model_name, values in summary.items():
        if model_name == "total_cost" or not isinstance(values, dict):
            continue
        prompt_tokens = int(values.get("prompt_tokens", 0) or 0)
        completion_tokens = int(values.get("completion_tokens", 0) or 0)
        total_tokens = int(values.get("total_tokens", prompt_tokens + completion_tokens) or 0)
        cost = round(float(values.get("cost", 0.0) or 0.0), 8)
        normalized["models"][model_name] = {
            "cost": cost,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        normalized["prompt_tokens"] += prompt_tokens
        normalized["completion_tokens"] += completion_tokens
        normalized["total_tokens"] += total_tokens

    return normalized


def _merge_usage_totals(base: dict[str, Any], addition: dict[str, Any]) -> dict[str, Any]:
    merged = {
        "total_cost": round(base["total_cost"] + addition["total_cost"], 8),
        "prompt_tokens": base["prompt_tokens"] + addition["prompt_tokens"],
        "completion_tokens": base["completion_tokens"] + addition["completion_tokens"],
        "total_tokens": base["total_tokens"] + addition["total_tokens"],
        "models": deepcopy(base["models"]),
    }
    for model_name, values in addition["models"].items():
        current = merged["models"].setdefault(
            model_name,
            {"cost": 0.0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
        current["cost"] = round(current["cost"] + values["cost"], 8)
        current["prompt_tokens"] += values["prompt_tokens"]
        current["completion_tokens"] += values["completion_tokens"]
        current["total_tokens"] += values["total_tokens"]
    return merged


def _extract_pipeline_data(messages: list[dict]) -> dict[str, Any]:
    """Try to extract structured JSON from agent messages."""
    data: dict[str, Any] = {
        "company_profile": {},
        "industry_analysis": {},
        "market_network": {},
        "quality_review": {},
        "synthesis": {},
        "validation_errors": [],
    }

    agent_to_key = {
        "CompanyIntelligence": "company_profile",
        "StrategicSignals": "industry_analysis",
        "MarketNetwork": "market_network",
        "EvidenceQA": "quality_review",
        "Synthesis": "synthesis",
    }
    key_to_model = {
        "company_profile": CompanyProfile,
        "industry_analysis": IndustryAnalysis,
        "market_network": MarketNetwork,
        "quality_review": QualityReview,
        "synthesis": SynthesisReport,
    }

    for msg in messages:
        agent = msg.get("agent", "")
        key = agent_to_key.get(agent)
        if not key:
            continue
        content = msg.get("content", "")
        parsed = _try_parse_json(content)
        if parsed is None:
            log.debug("No JSON parsed from %s (content len=%d)", agent, len(content))
            continue

        model = key_to_model[key]
        try:
            validated = model.model_validate(parsed)
        except ValidationError as exc:
            details = _format_validation_error(exc)
            data["validation_errors"].append(
                {
                    "agent": agent,
                    "section": key,
                    "details": details,
                }
            )
            log.warning("Schema validation failed for %s -> %s: %s", agent, key, details)
            continue

        log.debug("Parsed structured JSON from %s -> %s", agent, key)
        data[key] = validated.model_dump(mode="json")

    profile = data.get("company_profile", {})
    synthesis = data.get("synthesis", {})
    market = data.get("market_network", {})
    fallback_target_company = (
        profile.get("company_name")
        or synthesis.get("target_company")
        or "n/v"
    )
    if market and market.get("target_company") in ("", "n/v", None):
        market["target_company"] = fallback_target_company
    if synthesis and market:
        if not synthesis.get("total_peer_competitors"):
            synthesis["total_peer_competitors"] = len(market.get("peer_competitors", {}).get("companies", []))
        if not synthesis.get("total_downstream_buyers"):
            synthesis["total_downstream_buyers"] = len(market.get("downstream_buyers", {}).get("companies", []))
        if not synthesis.get("total_service_providers"):
            synthesis["total_service_providers"] = len(market.get("service_providers", {}).get("companies", []))
        if not synthesis.get("total_cross_industry_buyers"):
            synthesis["total_cross_industry_buyers"] = len(market.get("cross_industry_buyers", {}).get("companies", []))

    _apply_quality_guardrails(data)
    return data


def _apply_quality_guardrails(data: dict[str, Any]) -> None:
    """Add deterministic QA findings for stale sources and weak buyer evidence."""
    quality = data.setdefault("quality_review", {})
    synthesis = data.setdefault("synthesis", {})
    profile = data.get("company_profile", {})
    industry = data.get("industry_analysis", {})
    market = data.get("market_network", {})

    quality.setdefault("validated_agents", [])
    quality.setdefault("evidence_health", "n/v")
    quality.setdefault("open_gaps", [])
    quality.setdefault("recommendations", [])
    synthesis.setdefault("key_risks", [])
    synthesis.setdefault("next_steps", [])

    gaps = list(quality.get("open_gaps", []))
    recommendations = list(quality.get("recommendations", []))
    key_risks = list(synthesis.get("key_risks", []))
    next_steps = list(synthesis.get("next_steps", []))
    severity = 0

    company_sources = _analyze_sources(profile.get("sources", []), COMPANY_SOURCE_MAX_AGE_DAYS)
    if profile:
        if company_sources["total"] == 0:
            severity += 2
            gaps.append("CompanyIntelligence: Firmenprofil ohne zitierte Quellen.")
            recommendations.append("CompanyIntelligence: Primärquellen wie Website, Impressum, Jahresbericht oder Registerauszug ergänzen.")
        elif company_sources["fresh"] == 0:
            severity += 2
            gaps.append("CompanyIntelligence: Firmenprofil stützt sich auf veraltete Quellen für volatile Fakten.")
            recommendations.append("CompanyIntelligence: Umsatz, Profitabilität und aktuelle Ereignisse mit frischen Primärquellen aktualisieren.")
            if profile.get("revenue") not in ("", "n/v", None):
                profile["revenue"] = "n/v"
            economic = profile.get("economic_situation", {})
            if isinstance(economic, dict):
                for key in ("revenue_trend", "profitability", "financial_pressure"):
                    if economic.get(key) not in ("", "n/v", None):
                        economic[key] = "n/v"

    industry_sources = _analyze_sources(industry.get("sources", []), INDUSTRY_SOURCE_MAX_AGE_DAYS)
    if industry:
        if industry_sources["total"] == 0:
            severity += 2
            gaps.append("StrategicSignals: Branchenanalyse ohne belastbare Marktquellen.")
            recommendations.append("StrategicSignals: Aktuelle Branchenquellen aus den letzten 12-18 Monaten ergänzen.")
            for key in ("market_size", "growth_rate"):
                if industry.get(key) not in ("", "n/v", None):
                    industry[key] = "n/v"
        elif industry_sources["fresh"] == 0:
            severity += 2
            gaps.append("StrategicSignals: Branchenanalyse basiert auf veralteten Marktquellen.")
            recommendations.append("StrategicSignals: Marktgröße, Wachstum und Nachfrageausblick mit frischen Branchenquellen aktualisieren.")
            for key in ("market_size", "growth_rate", "demand_outlook"):
                if industry.get(key) not in ("", "n/v", None):
                    industry[key] = "n/v"

    buyer_strength = _enforce_buyer_evidence(market)
    severity += buyer_strength["severity"]
    gaps.extend(buyer_strength["gaps"])
    recommendations.extend(buyer_strength["recommendations"])

    if company_sources["fresh"] == 0 and company_sources["total"] > 0:
        key_risks.append("Kern-Firmendaten basieren auf veralteten Quellen und sind für volatile Kennzahlen nicht belastbar.")
        next_steps.append("Vor dem Termin frische Primärquellen für Umsatz, Profitabilität und aktuelle Ereignisse prüfen.")
    if industry_sources["fresh"] == 0:
        key_risks.append("Markt- und Nachfragesignale sind nicht aktuell genug für belastbare Schlüsse.")
        next_steps.append("Aktuelle Branchenreports oder Primärdaten zur Nachfrage- und Überkapazitätslage nachrecherchieren.")
    if buyer_strength["severity"] > 0:
        key_risks.append("Das Käufernetzwerk ist evidenzseitig zu schwach oder zu kandidat-lastig für harte Marktbehauptungen.")
        next_steps.append("Buyer-Longlist nur mit qualifizierten oder verifizierten Treffern aus Primärquellen nachschärfen.")
        summary = synthesis.get("buyer_market_summary", "")
        if summary:
            synthesis["buyer_market_summary"] = f"{summary} Evidenzseitig ist das Käufernetzwerk derzeit nur eingeschränkt belastbar."

    quality["open_gaps"] = _dedupe_strings(gaps)
    quality["recommendations"] = _dedupe_strings(recommendations)
    synthesis["key_risks"] = _dedupe_strings(key_risks)
    synthesis["next_steps"] = _dedupe_strings(next_steps)
    quality["evidence_health"] = _merge_evidence_health(quality.get("evidence_health", "n/v"), severity)


def _enforce_buyer_evidence(market: dict[str, Any]) -> dict[str, Any]:
    severity = 0
    gaps: list[str] = []
    recommendations: list[str] = []
    strong_buyers = 0
    total_buyers = 0

    for tier_name, label in (
        ("peer_competitors", "Peer Competitors"),
        ("downstream_buyers", "Downstream Buyers"),
        ("service_providers", "Service Providers"),
        ("cross_industry_buyers", "Cross-Industry Buyers"),
    ):
        tier = market.get(tier_name, {})
        if not isinstance(tier, dict):
            continue
        tier_sources = tier.get("sources", [])
        tier_source_info = _analyze_sources(tier_sources, BUYER_SOURCE_MAX_AGE_DAYS)
        companies = tier.get("companies", [])
        if not isinstance(companies, list):
            continue

        if companies and tier_source_info["total"] == 0:
            severity += 1
            gaps.append(f"MarketNetwork: {label} enthält Käufer ohne tierweite Quellen.")
            recommendations.append(f"MarketNetwork: {label} mit konkreten Quellen oder direkter Buyer-Evidenz belegen.")
        elif companies and tier_source_info["fresh"] == 0:
            severity += 1
            gaps.append(f"MarketNetwork: {label} basiert auf veralteten Quellen.")
            recommendations.append(f"MarketNetwork: {label} mit frischer Buyer-Evidenz aktualisieren.")

        for buyer in companies:
            if not isinstance(buyer, dict):
                continue
            total_buyers += 1
            buyer_source = buyer.get("source")
            buyer_source_info = _analyze_sources([buyer_source] if buyer_source else [], BUYER_SOURCE_MAX_AGE_DAYS)
            has_usable_source = (buyer_source_info["fresh"] > 0) or (tier_source_info["fresh"] > 0)
            if buyer.get("evidence_tier") in {"qualified", "verified"} and not has_usable_source:
                buyer["evidence_tier"] = "candidate"
            if buyer.get("evidence_tier") in {"qualified", "verified"}:
                strong_buyers += 1

    peer_count = len(market.get("peer_competitors", {}).get("companies", [])) if isinstance(market.get("peer_competitors"), dict) else 0
    downstream_count = len(market.get("downstream_buyers", {}).get("companies", [])) if isinstance(market.get("downstream_buyers"), dict) else 0
    if peer_count == 0:
        severity += 1
        gaps.append("MarketNetwork: Keine belastbaren Peer-Competitors identifiziert.")
        recommendations.append("MarketNetwork: Wettbewerber mit ähnlichen Produkten und konkreten Überschneidungen ergänzen.")
    if downstream_count == 0:
        severity += 1
        gaps.append("MarketNetwork: Keine belastbaren Downstream-Buyer identifiziert.")
        recommendations.append("MarketNetwork: Abnehmer oder Aftermarket-Käufer mit klarer Produktpassung ergänzen.")
    if total_buyers > 0 and strong_buyers == 0:
        severity += 2
        gaps.append("MarketNetwork: Buyer-Liste ist komplett kandidat-basiert und nicht belastbar.")
        recommendations.append("MarketNetwork: Mindestens einige Buyer mit qualifizierter oder verifizierter Evidenz absichern.")
    elif total_buyers > 0 and strong_buyers < max(2, total_buyers // 2):
        severity += 1
        gaps.append("MarketNetwork: Buyer-Liste ist überwiegend kandidat-lastig.")
        recommendations.append("MarketNetwork: Die wichtigsten Buyer-Tiers mit stärkerer Evidenz absichern.")

    return {
        "severity": severity,
        "gaps": gaps,
        "recommendations": recommendations,
    }


def _analyze_sources(sources: Any, max_age_days: int) -> dict[str, int]:
    total = 0
    fresh = 0
    stale = 0
    undated = 0

    for source in _as_list(sources):
        if not isinstance(source, dict):
            continue
        total += 1
        parsed = _parse_accessed_date(source.get("accessed", ""))
        if parsed is None:
            undated += 1
            continue
        age_days = (datetime.now(timezone.utc).date() - parsed).days
        if age_days <= max_age_days:
            fresh += 1
        else:
            stale += 1

    return {
        "total": total,
        "fresh": fresh,
        "stale": stale,
        "undated": undated,
    }


def _parse_accessed_date(value: Any):
    text = str(value or "").strip()
    if not text:
        return None
    candidates = [
        text.replace("Z", "+00:00"),
        f"{text}-01" if re.fullmatch(r"\d{4}-\d{2}", text) else "",
        f"{text}-01-01" if re.fullmatch(r"\d{4}", text) else "",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            continue
    return None


def _merge_evidence_health(current: str, severity: int) -> str:
    normalized = str(current or "n/v").strip().lower()
    ranking = {
        "hoch": 3,
        "high": 3,
        "mittel": 2,
        "medium": 2,
        "niedrig": 1,
        "low": 1,
        "n/v": 0,
        "unklar": 0,
    }
    current_rank = ranking.get(normalized, 0)
    target_rank = current_rank
    if severity >= 5:
        target_rank = min(current_rank or 3, 1)
    elif severity >= 2:
        target_rank = min(current_rank or 3, 2)
    elif severity == 0 and current_rank == 0:
        target_rank = 2
    label_by_rank = {
        3: "hoch",
        2: "mittel",
        1: "niedrig",
        0: "n/v",
    }
    return label_by_rank[target_rank]


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _normalize_chat_history(chat_result: Any) -> list[dict[str, str]]:
    """Convert a chat result into the minimal message format used by extraction."""
    chat_history = []
    if hasattr(chat_result, "chat_history"):
        chat_history = chat_result.chat_history
    elif isinstance(chat_result, dict):
        chat_history = chat_result.get("chat_history", [])

    normalized = []
    for msg in chat_history or []:
        normalized.append(
            {
                "agent": msg.get("name", msg.get("role", "unknown")),
                "content": msg.get("content", "") or "",
            }
        )
    return normalized


def _format_validation_error(exc: ValidationError) -> str:
    """Create a compact validation error summary for logs and UI."""
    errors = []
    for issue in exc.errors(include_url=False):
        location = ".".join(str(part) for part in issue.get("loc", ())) or "root"
        message = issue.get("msg", "invalid value")
        errors.append(f"{location}: {message}")
    if not errors:
        return "root: validation failed"
    return "; ".join(errors[:3])


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    if value in (None, ""):
        return []
    return [value]


def _try_parse_json(text: str) -> dict | None:
    """Try to extract JSON from text that may contain markdown fences."""
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, TypeError):
            pass
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except (json.JSONDecodeError, TypeError):
                        pass
                    break
    return None
