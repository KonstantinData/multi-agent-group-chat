"""Liquisto Briefing UI — pre-meeting preparation dashboard."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.app.use_cases import build_standard_backlog
from src.config import summarize_runtime_models
from src.exporters.pdf_report import generate_pdf
from src.orchestration.follow_up import answer_follow_up, load_run_artifact
from src.pipeline_runner import AGENT_META, PIPELINE_STEPS, run_pipeline


RUNS_DIR = PROJECT_ROOT / "artifacts" / "runs"
BACKLOG = build_standard_backlog()

st.set_page_config(page_title="Liquisto Briefing", page_icon="📋", layout="wide")

_SERVICE_LABELS = {
    "excess_inventory": "Überschuss-Inventar-Verwertung",
    "repurposing": "Repurposing & Kreislaufwirtschaft",
    "analytics": "Analytics & Entscheidungsunterstützung",
    "further_validation_required": "Weitere Validierung erforderlich",
}
_SERVICE_ICONS = {
    "excess_inventory": "📦",
    "repurposing": "♻️",
    "analytics": "📊",
    "further_validation_required": "🔍",
}
_SERVICE_DESCRIPTIONS = {
    "excess_inventory": "Wiederverkauf, Redeployment und Sekundärmarktpfade für Güter und Anlagen",
    "repurposing": "Kreislaufwirtschaft und Nachnutzungspfade für Materialien und Komponenten",
    "analytics": "Lagertransparenz, Entscheidungsunterstützung und operative Berichtsverbesserungen",
}
_GOODS_LABELS = {
    "manufacturer": "Hersteller",
    "distributor": "Händler / Großhändler",
    "held_in_stock": "Lagerhalter",
    "mixed": "Gemischt (Herstellung + Handel)",
    "unclear": "Geschäftsmodell unklar",
    "n/v": "",
}
_CONFIDENCE_BADGE = {
    "high": "🟢 Hohe Konfidenz",
    "medium": "🟡 Mittlere Konfidenz",
    "low": "🔴 Geringe Konfidenz",
}


def _init_state() -> None:
    defaults = {
        "running": False,
        "done": False,
        "pipeline_started": False,
        "messages": [],
        "pipeline_data": {},
        "run_context": {},
        "usage": {},
        "budget": {},
        "status": None,
        "error": None,
        "run_id": None,
        "input_company": "",
        "input_domain": "",
        "worker_queue": None,
        "follow_up_answer": None,
        "loaded_notice": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _drain_queue() -> None:
    worker_queue = st.session_state.worker_queue
    if worker_queue is None:
        return
    while True:
        try:
            item = worker_queue.get_nowait()
        except Empty:
            break
        event = item.get("event")
        if event == "message":
            st.session_state.messages.append(item["payload"])
        elif event == "result":
            payload = item["payload"]
            st.session_state.pipeline_data = payload["pipeline_data"]
            st.session_state.run_context = payload["run_context"]
            st.session_state.usage = payload.get("usage", {})
            st.session_state.budget = payload.get("budget", {})
            st.session_state.status = payload.get("status")
            st.session_state.run_id = payload.get("run_id")
            st.session_state.error = payload.get("error")
            st.session_state.done = True
            st.session_state.running = False
            st.session_state.pipeline_started = False
            st.session_state.worker_queue = None
        elif event == "error":
            st.session_state.error = item["payload"]
            st.session_state.done = True
            st.session_state.running = False
            st.session_state.pipeline_started = False
            st.session_state.worker_queue = None


def _run_dirs() -> list[Path]:
    if not RUNS_DIR.exists():
        return []
    return sorted([p for p in RUNS_DIR.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)


def _load_run(run_id: str) -> None:
    artifact = load_run_artifact(run_id)
    history_path = artifact["run_dir"] / "chat_history.json"
    messages = []
    if history_path.exists():
        raw = json.loads(history_path.read_text(encoding="utf-8"))
        messages = [
            {"agent": item.get("name", "Agent"), "content": item.get("content", ""), "type": "agent_message"}
            for item in raw
        ]
    st.session_state.running = False
    st.session_state.done = True
    st.session_state.pipeline_started = False
    st.session_state.messages = messages
    st.session_state.pipeline_data = artifact["pipeline_data"]
    st.session_state.run_context = artifact["run_context"]
    st.session_state.run_id = run_id
    st.session_state.status = artifact["run_context"].get("status")
    st.session_state.error = None
    st.session_state.worker_queue = None
    st.session_state.loaded_notice = run_id


def _message_preview(content: str, limit: int = 140) -> str:
    text = str(content or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text or "(empty)"
    return text[:limit].rstrip() + "..."


def _step_progress() -> tuple[int, str]:
    if not st.session_state.messages:
        return 0, "Waiting to start"
    current_step, current_label = 1, "Supervisor intake and routing"
    for m in st.session_state.messages:
        agent = m.get("agent", "")
        if agent.startswith("Company"):
            current_step, current_label = 2, "Company Department active"
        elif agent.startswith("Market"):
            current_step, current_label = 3, "Market Department active"
        elif agent.startswith("Buyer"):
            current_step, current_label = 4, "Buyer Department active"
        elif agent.startswith("Contact"):
            current_step, current_label = 5, "Contact Intelligence active"
        elif agent.startswith("Synthesis") or agent == "SynthesisDepartment":
            current_step, current_label = 6, "Strategic Synthesis active"
        elif agent == "ReportWriter":
            current_step, current_label = 7, "Report packaging active"
    if st.session_state.done:
        return 7, "Run completed"
    return current_step, current_label


def _task_rows() -> list[dict]:
    statuses = st.session_state.run_context.get("short_term_memory", {}).get("task_statuses", {})
    return [
        {"label": item["label"], "assignee": item["assignee"], "status": statuses.get(item["task_key"], "pending")}
        for item in BACKLOG
    ]


def _department_packages() -> dict[str, dict]:
    return st.session_state.run_context.get("short_term_memory", {}).get("department_packages", {})


def _render_message_feed() -> None:
    for m in reversed(st.session_state.messages[-40:]):
        agent = m.get("agent", "Agent")
        content = m.get("content", "")
        meta = AGENT_META.get(agent, {"summary": "", "icon": "[]"})
        title = f"{meta.get('icon', '[]')} {agent} - {_message_preview(content)}"
        with st.expander(title, expanded=False):
            st.code(content[:12000], language="json")


def _ranked_service_paths(synthesis: dict) -> list[dict]:
    """Return service_relevance items: positive first (ordered by recommended_paths), then unclear."""
    service_relevance = synthesis.get("liquisto_service_relevance", [])
    recommended = synthesis.get("recommended_engagement_paths", [])
    positive = [item for item in service_relevance if item.get("relevance") != "unclear"]
    unclear = [item for item in service_relevance if item.get("relevance") == "unclear"]
    if recommended and recommended[0] != "further_validation_required":
        positive = sorted(
            positive,
            key=lambda x: recommended.index(x["service_area"]) if x["service_area"] in recommended else 99,
        )
    return positive + unclear


def _render_briefing_tab() -> None:
    """Primary pre-meeting view: what matters, why, what to do, which Liquisto offer fits."""
    pipeline_data = st.session_state.pipeline_data
    synthesis = pipeline_data.get("synthesis", {})
    company = pipeline_data.get("company_profile", {})
    industry = pipeline_data.get("industry_analysis", {})
    market = pipeline_data.get("market_network", {})
    contacts_section = pipeline_data.get("contact_intelligence", {})
    quality = pipeline_data.get("quality_review", {})

    company_name = company.get("company_name", "n/v")
    industry_name = company.get("industry") or industry.get("industry_name", "")
    goods_type = _GOODS_LABELS.get(company.get("goods_classification", "n/v"), "")
    confidence = synthesis.get("confidence") or quality.get("evidence_health", "low")
    description = str(company.get("description", "") or "")

    # ── Company snapshot ─────────────────────────────────────────────────────
    st.markdown(f"## {company_name}")
    tag_parts = [p for p in [industry_name, goods_type] if p and p not in ("n/v", "")]
    caption_parts = [" · ".join(tag_parts), _CONFIDENCE_BADGE.get(confidence, "")]
    caption_line = "   ".join(p for p in caption_parts if p)
    if caption_line:
        st.caption(caption_line)
    if description and description != "n/v":
        st.write(description[:400] + ("..." if len(description) > 400 else ""))

    econ = company.get("economic_situation", {})
    econ_assessment = econ.get("assessment", "") if isinstance(econ, dict) else ""
    if econ_assessment and econ_assessment not in ("n/v", ""):
        st.info(f"**Wirtschaftliches Signal:** {econ_assessment}")

    st.divider()

    # ── Liquisto recommendation ───────────────────────────────────────────────
    st.markdown("### Liquisto-Empfehlung")
    ranked = _ranked_service_paths(synthesis)

    if not ranked:
        st.warning("Keine ausreichende Datenbasis für eine Empfehlung — Recherche vertiefen oder Follow-up nutzen.")
    else:
        primary = ranked[0]
        parea = primary.get("service_area", "")
        plabel = _SERVICE_LABELS.get(parea, parea.replace("_", " ").title())
        picon = _SERVICE_ICONS.get(parea, "📌")
        preasoning = primary.get("reasoning") or synthesis.get("opportunity_assessment_summary", "")

        with st.container(border=True):
            st.markdown(f"#### {picon} {plabel}")
            st.caption("Primäre Empfehlung")
            if preasoning and preasoning not in ("n/v", ""):
                st.write(preasoning)
            pdesc = _SERVICE_DESCRIPTIONS.get(parea, "")
            if pdesc:
                st.caption(pdesc)

        if len(ranked) > 1:
            secondary = ranked[1]
            sarea = secondary.get("service_area", "")
            slabel = _SERVICE_LABELS.get(sarea, sarea.replace("_", " ").title())
            sicon = _SERVICE_ICONS.get(sarea, "📌")
            sreasoning = secondary.get("reasoning", "")

            has_third = len(ranked) > 2
            if has_third:
                col_sec, col_low = st.columns([2, 1])
            else:
                col_sec = st.columns(1)[0]
                col_low = None

            with col_sec:
                with st.container(border=True):
                    st.markdown(f"**{sicon} {slabel}**")
                    st.caption("Zweite Option")
                    if sreasoning and sreasoning not in ("n/v", ""):
                        st.caption(sreasoning[:200])

            if has_third and col_low is not None:
                third = ranked[2]
                tarea = third.get("service_area", "")
                tlabel = _SERVICE_LABELS.get(tarea, tarea.replace("_", " ").title())
                with col_low:
                    with st.container(border=True):
                        st.markdown(f"**{tlabel}**")
                        st.caption("Aktuell weniger relevant")
                        reasoning_text = third.get("reasoning", "")
                        if reasoning_text:
                            st.caption(reasoning_text[:140])

    gen_mode = synthesis.get("generation_mode", "normal")
    if gen_mode == "fallback":
        st.caption("_Empfehlung basiert auf strukturierter Datenauswertung (kein AG2-Syntheselauf)._")

    st.divider()

    # ── Meeting preparation ───────────────────────────────────────────────────
    col_talk, col_validate = st.columns(2)

    with col_talk:
        st.markdown("### Im Termin ansprechen")
        next_steps = synthesis.get("next_steps", [])
        buyer_summary = market.get("downstream_buyers", {}).get("assessment", "")
        peer_count = len(market.get("peer_competitors", {}).get("companies", []))

        points: list[str] = []
        for step in next_steps[:4]:
            if step and step != "n/v":
                points.append(step)
        if buyer_summary and buyer_summary not in ("n/v", "") and len(points) < 4:
            points.append(f"Käufermarkt: {buyer_summary[:200]}")
        if peer_count > 0 and len(points) < 4:
            points.append(f"{peer_count} Wettbewerber identifiziert — Marktpositionierung ansprechen.")

        if points:
            for point in points[:4]:
                st.write(f"- {point}")
        else:
            st.caption("Keine spezifischen Gesprächspunkte verfügbar.")

    with col_validate:
        st.markdown("### Im Termin validieren")
        key_risks = synthesis.get("key_risks", [])
        open_gaps = quality.get("open_gaps", [])
        hypotheses: list[str] = []
        for risk in key_risks[:3]:
            if risk and risk != "n/v":
                hypotheses.append(risk)
        for gap in open_gaps[:2]:
            if gap and gap not in hypotheses and gap != "n/v":
                hypotheses.append(gap)

        if hypotheses:
            for h in hypotheses[:4]:
                st.write(f"- {h}")
        else:
            st.caption("Keine offenen Validierungspunkte identifiziert.")

    st.divider()

    # ── Contacts ──────────────────────────────────────────────────────────────
    st.markdown("### Kontakte")
    prioritized = contacts_section.get("prioritized_contacts") or contacts_section.get("contacts", [])
    if prioritized:
        contact_cols = st.columns(min(len(prioritized[:3]), 3))
        for i, contact in enumerate(prioritized[:3]):
            with contact_cols[i]:
                with st.container(border=True):
                    name = contact.get("name", "n/v")
                    role = contact.get("rolle_titel") or contact.get("funktion", "n/v")
                    firm = contact.get("firma", "")
                    seniority = contact.get("senioritaet", "")
                    outreach = contact.get("suggested_outreach_angle", "")
                    st.markdown(f"**{name}**")
                    meta_parts = [p for p in [role, firm] if p and p != "n/v"]
                    if meta_parts:
                        st.caption(" · ".join(meta_parts))
                    if seniority and seniority != "n/v":
                        st.caption(f"Seniorität: {seniority}")
                    if outreach and outreach != "n/v":
                        st.info(f"Outreach: {outreach}")
        if len(prioritized) > 3:
            st.caption(f"_+{len(prioritized) - 3} weitere Kontakte in der Recherche-Ansicht_")
    else:
        st.caption("Keine verifizierten Kontakte gefunden — ContactDepartment-Ergebnisse im Recherche-Tab prüfen.")

    st.divider()

    # ── Next action ───────────────────────────────────────────────────────────
    st.markdown("### Empfohlener nächster Schritt")
    next_steps_all = synthesis.get("next_steps", [])
    if next_steps_all:
        st.success(next_steps_all[0])
    else:
        readiness_reasons = pipeline_data.get("research_readiness", {}).get("reasons", [])
        if readiness_reasons:
            st.info(readiness_reasons[0])
        else:
            st.info("Follow-up durchführen oder Termin mit dem Kunden ansetzen.")


def _render_research_tab() -> None:
    """Secondary: detailed research depth per section."""
    pipeline_data = st.session_state.pipeline_data
    company = pipeline_data.get("company_profile", {})
    industry = pipeline_data.get("industry_analysis", {})
    market = pipeline_data.get("market_network", {})
    contacts_section = pipeline_data.get("contact_intelligence", {})

    with st.expander("Unternehmensprofil", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Name:** {company.get('company_name', 'n/v')}")
            st.write(f"**Website:** {company.get('website', 'n/v')}")
            st.write(f"**Branche:** {company.get('industry', 'n/v')}")
            goods_label = _GOODS_LABELS.get(company.get("goods_classification", "n/v"), "")
            if goods_label:
                st.write(f"**Gütertyp:** {goods_label}")
        with col2:
            products = company.get("products_and_services", [])
            if products:
                st.write("**Produkte / Leistungen:**")
                for p in products[:6]:
                    st.write(f"- {p}")
        desc = str(company.get("description", "") or "")
        if desc and desc != "n/v":
            st.write(desc)
        econ = company.get("economic_situation", {})
        if isinstance(econ, dict) and (econ.get("assessment") or econ.get("recent_events")):
            st.markdown("**Wirtschaftliche Signale:**")
            if econ.get("assessment") and econ["assessment"] != "n/v":
                st.write(econ["assessment"])
            for evt in econ.get("recent_events", [])[:5]:
                st.write(f"- {evt}")
            for sig in econ.get("inventory_signals", [])[:4]:
                st.write(f"- {sig}")
        scope = company.get("product_asset_scope", [])
        if scope:
            st.markdown("**Asset-Scope:**")
            for item in scope[:8]:
                st.write(f"- {item}")

    with st.expander("Markt und Industrie"):
        st.write(f"**Branche:** {industry.get('industry_name', 'n/v')}")
        assessment = str(industry.get("assessment", "") or "")
        if assessment and assessment != "n/v":
            st.write(assessment)
        demand = industry.get("demand_outlook", "")
        if demand and demand != "n/v":
            st.write(f"**Nachfrage-Outlook:** {demand}")
        for trend in industry.get("key_trends", [])[:5]:
            st.write(f"- {trend}")
        repurposing = industry.get("repurposing_signals", [])
        if repurposing:
            st.markdown("**Repurposing-Signale:**")
            for item in repurposing[:5]:
                st.write(f"- {item}")
        analytics = industry.get("analytics_signals", [])
        if analytics:
            st.markdown("**Analytics-Signale:**")
            for item in analytics[:5]:
                st.write(f"- {item}")

    with st.expander("Käufer- und Wettbewerbernetzwerk"):
        peers = market.get("peer_competitors", {})
        if peers:
            peer_assessment = peers.get("assessment", "")
            if peer_assessment and peer_assessment != "n/v":
                st.markdown(f"**Wettbewerber** — {peer_assessment[:300]}")
            for company_item in peers.get("companies", [])[:10]:
                if isinstance(company_item, dict):
                    name = company_item.get("name", "")
                    country = company_item.get("country", "")
                    relevance = company_item.get("relevance", "")
                    parts = [name]
                    if country and country != "n/v":
                        parts.append(f"({country})")
                    if relevance and relevance != "n/v":
                        parts.append(f"— {relevance}")
                    line = " ".join(p for p in parts if p)
                    if line.strip():
                        st.write(f"- {line}")
                elif company_item:
                    st.write(f"- {company_item}")
        buyers = market.get("downstream_buyers", {})
        if buyers:
            buyer_assessment = buyers.get("assessment", "")
            if buyer_assessment and buyer_assessment != "n/v":
                st.markdown(f"**Downstream-Käufer** — {buyer_assessment[:300]}")
            for buyer in buyers.get("companies", [])[:10]:
                if isinstance(buyer, dict):
                    name = buyer.get("name", "")
                    country = buyer.get("country", "")
                    line = name + (f" ({country})" if country and country != "n/v" else "")
                    if line.strip():
                        st.write(f"- {line}")
                elif buyer:
                    st.write(f"- {buyer}")
        monetization = market.get("monetization_paths", [])
        if monetization:
            st.markdown("**Monetisierungspfade:**")
            for path in monetization[:5]:
                st.write(f"- {path}")
        redeployment = market.get("redeployment_paths", [])
        if redeployment:
            st.markdown("**Redeployment-Pfade:**")
            for path in redeployment[:5]:
                st.write(f"- {path}")

    with st.expander("Kontakt-Intelligence"):
        narrative = str(contacts_section.get("narrative_summary", "") or "")
        if narrative and narrative != "n/v":
            st.write(narrative)
        coverage = contacts_section.get("coverage_quality", "n/v")
        st.caption(f"Abdeckungsqualität: {coverage}")
        all_contacts = contacts_section.get("prioritized_contacts") or contacts_section.get("contacts", [])
        if all_contacts:
            for c in all_contacts:
                name = c.get("name", "n/v")
                role = c.get("rolle_titel") or c.get("funktion", "n/v")
                firm = c.get("firma", "n/v")
                with st.expander(f"{name} — {role} @ {firm}"):
                    st.write(f"**Funktion:** {c.get('funktion', 'n/v')}")
                    st.write(f"**Seniorität:** {c.get('senioritaet', 'n/v')}")
                    st.write(f"**Confidence:** {c.get('confidence', 'n/v')}")
                    st.write(f"**Relevanz:** {c.get('relevance_reason', 'n/v')}")
                    outreach = c.get("suggested_outreach_angle", "")
                    if outreach and outreach != "n/v":
                        st.info(f"**Outreach-Angle:** {outreach}")
        else:
            st.caption("Keine Kontakte gefunden.")


def _render_follow_up_panel() -> None:
    current_run_id = st.session_state.run_id or ""
    st.markdown(
        "Stelle gezielte Fragen zu einem abgeschlossenen Run. Der **Question Router** entscheidet, "
        "welches Department antwortet (Company, Market, Buyer, Contact Intelligence, Synthesis)."
    )
    with st.form("follow_up_form", clear_on_submit=False):
        run_id = st.text_input("Run ID", value=current_run_id, help="z.B. 20250322T143012Z")
        question = st.text_area(
            "Folgefrage",
            placeholder=(
                "z.B. 'Welche Ansprechpartner gibt es bei Bosch?' "
                "oder 'Welche Drucksignale wurden bei der Marktanalyse gefunden?'"
            ),
        )
        submitted = st.form_submit_button("Frage beantworten", use_container_width=True)

    if submitted:
        if not run_id.strip() or not question.strip():
            st.warning("Run ID und Frage sind erforderlich.")
        else:
            with st.spinner("Routing und Antwort wird vorbereitet..."):
                try:
                    artifact = load_run_artifact(run_id.strip())
                    from src.agents.supervisor import SupervisorAgent
                    supervisor = SupervisorAgent()
                    route = supervisor.route_question(question=question.strip(), source="user_ui")
                    answer = answer_follow_up(
                        run_id=run_id.strip(),
                        route=route["route"],
                        question=question.strip(),
                        pipeline_data=artifact["pipeline_data"],
                        run_context=artifact["run_context"],
                    )
                    st.session_state.follow_up_answer = {**answer, "route_reason": route["reason"]}
                except FileNotFoundError:
                    st.error(f"Run '{run_id.strip()}' nicht gefunden.")
                except Exception as exc:
                    st.error(f"Fehler: {exc}")

    answer = st.session_state.follow_up_answer
    if answer:
        dept_icons = {
            "CompanyDepartment": "🏢",
            "MarketDepartment": "📡",
            "BuyerDepartment": "🌐",
            "ContactDepartment": "👤",
            "SynthesisDepartment": "🧠",
        }
        routed_to = answer.get("routed_to", "n/v")
        icon = dept_icons.get(routed_to, "🔍")
        with st.container(border=True):
            st.markdown(f"**{icon} Beantwortet von: {routed_to}**")
            st.caption(answer.get("route_reason", ""))
            st.write(answer.get("answer", "n/v"))
            col_a, col_b = st.columns(2)
            with col_a:
                if answer.get("evidence_used"):
                    st.write("**Verwendete Belege**")
                    for item in answer["evidence_used"]:
                        if item:
                            st.write(f"- {item[:200]}")
            with col_b:
                if answer.get("unresolved_points"):
                    st.write("**Offene Punkte**")
                    for item in answer["unresolved_points"]:
                        st.write(f"- {item}")


def _render_pipeline_tab() -> None:
    """Technical internals for QA and debugging."""
    pipeline_data = st.session_state.pipeline_data
    quality = pipeline_data.get("quality_review", {})
    readiness = pipeline_data.get("research_readiness", {})

    with st.expander("Recherche-Qualität & Evidenz"):
        col1, col2, col3 = st.columns(3)
        col1.metric("Readiness-Score", readiness.get("score", "n/v"))
        col2.metric("Evidenz-Qualität", quality.get("evidence_health", "n/v"))
        col3.metric("Status", st.session_state.status or "n/v")
        if readiness.get("reasons"):
            for r in readiness["reasons"]:
                st.write(f"- {r}")
        if quality.get("open_gaps"):
            st.markdown("**Offene Lücken:**")
            for g in quality["open_gaps"][:10]:
                st.write(f"- {g}")

    with st.expander("Task-Status"):
        status_icons = {"accepted": "✅", "degraded": "🟡", "rejected": "❌", "skipped": "⏭️", "pending": "⏳"}
        for row in _task_rows():
            icon = status_icons.get(row["status"], "·")
            st.write(f"{icon} {row['label']} — `{row['assignee']}` — `{row['status']}`")

    packages = _department_packages()
    if packages:
        with st.expander("Department-Pakete (intern)"):
            for dept_name, package in packages.items():
                st.markdown(f"**{dept_name}**")
                st.json(package)

    with st.expander("Run-Metadaten"):
        budget = st.session_state.budget
        st.json({
            "run_id": st.session_state.run_id,
            "llm_calls": budget.get("llm_calls_used"),
            "search_calls": budget.get("search_calls_used"),
            "page_fetches": budget.get("page_fetches_used"),
            "estimated_cost_usd": budget.get("estimated_cost_usd"),
            "elapsed_seconds": budget.get("elapsed_seconds"),
            "department_timings": budget.get("department_timings", {}),
        })


def _start_pipeline(company_name: str, web_domain: str) -> None:
    st.session_state.running = True
    st.session_state.done = False
    st.session_state.pipeline_started = False
    st.session_state.messages = []
    st.session_state.pipeline_data = {}
    st.session_state.run_context = {}
    st.session_state.usage = {}
    st.session_state.budget = {}
    st.session_state.status = None
    st.session_state.error = None
    st.session_state.run_id = None
    st.session_state.input_company = company_name
    st.session_state.input_domain = web_domain
    st.session_state.worker_queue = Queue()


_init_state()
_drain_queue()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Initial Run")
    company_name = st.text_input("Company name", value=st.session_state.get("input_company", ""))
    web_domain = st.text_input("Web domain", value=st.session_state.get("input_domain", ""))
    if st.button(
        "Start run",
        disabled=st.session_state.running or not company_name or not web_domain,
        use_container_width=True,
    ):
        _start_pipeline(company_name, web_domain)
        st.rerun()

    st.divider()
    run_dirs = _run_dirs()
    run_options = [p.name for p in run_dirs[:30]]
    selected_run = st.selectbox("Load run", options=[""] + run_options, index=0)
    if st.button(
        "Load selected run",
        disabled=st.session_state.running or not selected_run,
        use_container_width=True,
    ):
        _load_run(selected_run)
        st.rerun()

    st.divider()
    st.caption(f"Runtime models: {summarize_runtime_models()}")
    if st.session_state.run_id and st.session_state.pipeline_data:
        pdf_de = generate_pdf(st.session_state.pipeline_data, lang="de")
        st.download_button(
            "Download PDF (DE)",
            data=pdf_de,
            file_name=f"liquisto_briefing_{st.session_state.run_id}_DE.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        pdf_en = generate_pdf(st.session_state.pipeline_data, lang="en")
        st.download_button(
            "Download PDF (EN)",
            data=pdf_en,
            file_name=f"liquisto_briefing_{st.session_state.run_id}_EN.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


# ── Page header ───────────────────────────────────────────────────────────────
st.title("Liquisto Briefing")
st.caption("Gesprächsvorbereitung auf Basis strukturierter Markt- und Unternehmensrecherche")

# ── Live run view ─────────────────────────────────────────────────────────────
if st.session_state.running and not st.session_state.done:
    current_step, current_label = _step_progress()
    st.progress(current_step / len(PIPELINE_STEPS))
    st.write(current_label)

    cols = st.columns(len(PIPELINE_STEPS))
    for index, (agent_name, label) in enumerate(PIPELINE_STEPS):
        meta = AGENT_META.get(agent_name, {"icon": "[]", "color": "#d0d5dd"})
        active = index + 1 <= current_step
        background = meta["color"] if active else "#f2f4f7"
        text_color = "#ffffff" if active else "#101828"
        cols[index].markdown(
            f"""<div style="border:1px solid #d0d5dd;border-radius:14px;padding:12px;background:{background};min-height:110px;">
              <div style="font-size:26px;color:{text_color};">{meta['icon']}</div>
              <div style="font-weight:700;color:{text_color};margin-top:8px;">{label}</div>
              <div style="font-size:12px;color:{text_color};opacity:0.92;">{agent_name}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    worker_queue = st.session_state.worker_queue
    _company_name = st.session_state.get("input_company", "")
    _web_domain = st.session_state.get("input_domain", "")

    def _on_message(event: dict) -> None:
        worker_queue.put({"event": "message", "payload": event})

    def _run() -> None:
        try:
            result = run_pipeline(company_name=_company_name, web_domain=_web_domain, on_message=_on_message)
            worker_queue.put({"event": "result", "payload": result})
        except Exception as exc:
            worker_queue.put({"event": "error", "payload": str(exc)})

    if not st.session_state.pipeline_started:
        st.session_state.pipeline_started = True
        threading.Thread(target=_run, daemon=True).start()

    st.subheader("Live message feed")
    _render_message_feed()
    time.sleep(0.8)
    st.rerun()

# ── Error ─────────────────────────────────────────────────────────────────────
if st.session_state.error:
    st.error(st.session_state.error)

# ── Post-run display ──────────────────────────────────────────────────────────
if st.session_state.done and st.session_state.run_id:
    status = st.session_state.status
    company_label = st.session_state.pipeline_data.get("company_profile", {}).get("company_name", st.session_state.run_id)
    if status == "completed":
        st.success(f"Briefing bereit — {company_label}")
    elif status == "completed_partial":
        st.warning(f"Briefing mit Lücken — {company_label}")
    elif status == "completed_but_not_usable":
        st.error(f"Recherche unvollständig — Briefing eingeschränkt nutzbar ({company_label})")
    elif st.session_state.loaded_notice == st.session_state.run_id:
        st.info(f"Run geladen — {company_label}")

    tab_briefing, tab_research, tab_follow_up, tab_pipeline, tab_messages = st.tabs(
        ["Briefing", "Recherche", "Follow-up", "Pipeline", "Messages"]
    )

    with tab_briefing:
        _render_briefing_tab()

    with tab_research:
        _render_research_tab()

    with tab_follow_up:
        _render_follow_up_panel()

    with tab_pipeline:
        _render_pipeline_tab()

    with tab_messages:
        _render_message_feed()
