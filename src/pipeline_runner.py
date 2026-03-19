"""Pipeline runner with callback support for live UI updates."""
from __future__ import annotations

import json
import logging
import re
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

import autogen

from src.config import get_llm_config
from src.agents.definitions import create_agents, create_group_chat
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
    "CompanyIntelligence":  {"icon": "🏢", "color": "#198754"},
    "StrategicSignals":     {"icon": "📡", "color": "#6610f2"},
    "MarketNetwork":        {"icon": "🌐", "color": "#fd7e14"},
    "EvidenceQA":           {"icon": "🔍", "color": "#dc3545"},
    "Synthesis":            {"icon": "📋", "color": "#20c997"},
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


def run_pipeline(
    company_name: str,
    web_domain: str,
    on_message: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the full pipeline. Calls on_message(event) for each agent message."""

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

    # --- Step 1: Config ---
    log.info("=" * 60)
    log.info("PIPELINE START: %s (%s)", company_name, web_domain)
    log.info("=" * 60)
    _emit("debug", "System", f"Pipeline gestartet für: {company_name} ({web_domain})")

    try:
        log.debug("Loading LLM config...")
        llm_config = get_llm_config()
        model = llm_config["config_list"][0]["model"]
        log.info("LLM config loaded: model=%s", model)
        _emit("debug", "System", f"LLM Model: {model}")
    except Exception as e:
        log.error("Failed to load LLM config: %s", e)
        _emit("error", "System", f"LLM Config Fehler: {e}")
        raise

    # --- Step 2: Create agents ---
    try:
        log.debug("Creating agents...")
        agents = create_agents(llm_config)
        log.info("Agents created: %s", list(agents.keys()))
        _emit("debug", "System", f"Agenten erstellt: {', '.join(agents.keys())}")
    except Exception as e:
        log.error("Failed to create agents: %s", e)
        _emit("error", "System", f"Agent-Erstellung fehlgeschlagen: {e}")
        raise

    # --- Step 3: Create group chat ---
    try:
        log.debug("Creating group chat with FSM transitions...")
        groupchat, manager = create_group_chat(agents, llm_config)
        log.info("GroupChat created: %d agents, max_round=%d", len(groupchat.agents), groupchat.max_round)
        _emit("debug", "System", f"GroupChat erstellt: {len(groupchat.agents)} Agenten, max_round={groupchat.max_round}")
    except Exception as e:
        log.error("Failed to create group chat: %s", e)
        _emit("error", "System", f"GroupChat-Erstellung fehlgeschlagen: {e}")
        raise

    # --- Step 4: Hook message interception ---
    class _TrackedMessages(list):
        """List subclass that emits events on append."""
        def __init__(self, emit_fn):
            super().__init__()
            self._emit_fn = emit_fn
            self._count = 0

        def append(self, msg):
            super().append(msg)
            self._count += 1
            sender = msg.get("name", msg.get("role", "unknown"))
            content = msg.get("content", "") or ""
            role = msg.get("role", "?")
            log.info(
                "MSG #%d | sender=%-20s | role=%-10s | len=%d | preview=%.100s",
                self._count, sender, role, len(content), content.replace("\n", " ")[:100],
            )
            self._emit_fn("agent_message", sender, content)

    groupchat.messages = _TrackedMessages(_emit)
    log.debug("Message interception hook installed")

    # --- Step 5: Build task ---
    task = (
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
    log.info("Task built (%d chars)", len(task))
    _emit("debug", "System", "Task erstellt, starte Chat...")

    # --- Step 6: Run chat ---
    try:
        log.info(">>> Calling initiate_chat() ...")
        result = agents["admin"].initiate_chat(manager, message=task)
        n_msgs = len(collected_messages)
        log.info("<<< initiate_chat() returned. Collected messages: %d", n_msgs)
        _emit("debug", "System", f"Chat beendet. {n_msgs} Nachrichten.")
    except Exception as e:
        log.error("initiate_chat() FAILED: %s\n%s", e, traceback.format_exc())
        _emit("error", "System", f"Chat-Fehler: {e}")
        raise

    # --- Step 7: Export ---
    try:
        run_id = uuid.uuid4().hex[:12]
        run_dir = export_run(run_id, result)
        log.info("Exported to: %s", run_dir)
        _emit("debug", "System", f"Export: {run_dir}")
    except Exception as e:
        log.error("Export failed: %s", e)
        run_id = "export_failed"
        run_dir = ""

    # --- Step 8: Parse results ---
    pipeline_data = _extract_pipeline_data(collected_messages, company_name)
    filled = [k for k, v in pipeline_data.items() if v]
    log.info("Parsed pipeline data. Filled keys: %s", filled)
    _emit("debug", "System", f"Ergebnisse geparst: {', '.join(filled) or 'keine'}")

    log.info("=" * 60)
    log.info("PIPELINE DONE: run_id=%s, messages=%d", run_id, len(collected_messages))
    log.info("=" * 60)

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "messages": collected_messages,
        "pipeline_data": pipeline_data,
    }


def _extract_pipeline_data(messages: list[dict], company_name: str) -> dict[str, Any]:
    """Try to extract structured JSON from agent messages."""
    data: dict[str, Any] = {
        "company_profile": {},
        "industry_analysis": {},
        "market_network": {},
        "quality_review": {},
        "synthesis": {},
    }

    agent_to_key = {
        "CompanyIntelligence": "company_profile",
        "StrategicSignals": "industry_analysis",
        "MarketNetwork": "market_network",
        "EvidenceQA": "quality_review",
        "Synthesis": "synthesis",
    }

    for msg in messages:
        agent = msg.get("agent", "")
        key = agent_to_key.get(agent)
        if not key:
            continue
        content = msg.get("content", "")
        parsed = _try_parse_json(content)
        if parsed:
            log.debug("Parsed JSON from %s -> %s (%d keys)", agent, key, len(parsed))
            data[key] = parsed
        else:
            log.debug("No JSON parsed from %s (content len=%d)", agent, len(content))

    return data


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
