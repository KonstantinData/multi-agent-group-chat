"""Liquisto Market Intelligence Pipeline – Streamlit UI."""
from __future__ import annotations

import sys
import os
from pathlib import Path

# Ensure project root is on sys.path so 'src' is importable
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

import threading
import time
from datetime import datetime, timezone

import streamlit as st

# Must be first Streamlit call
st.set_page_config(
    page_title="Liquisto Market Intelligence",
    page_icon="🔍",
    layout="wide",
)

from src.pipeline_runner import run_pipeline, AGENT_META, PIPELINE_STEPS
from src.exporters.pdf_report import generate_pdf


# --- Session State Init ---

def _init_state():
    defaults = {
        "running": False,
        "done": False,
        "pipeline_started": False,
        "messages": [],
        "current_agent": None,
        "pipeline_data": {},
        "run_id": None,
        "error": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# --- Sidebar ---

with st.sidebar:
    st.image("https://www.liquisto.com/hubfs/Logos/liquisto-logo.svg", width=180)
    st.markdown("---")
    st.markdown("### Neue Recherche")
    company_name = st.text_input("Firmenname", placeholder="z.B. Lenze SE")
    web_domain = st.text_input("Web Domain", placeholder="z.B. lenze.com")

    start_disabled = st.session_state.running or not company_name or not web_domain
    start_btn = st.button(
        "🚀 Pipeline starten",
        disabled=start_disabled,
        use_container_width=True,
        type="primary",
    )

    if st.session_state.done:
        st.markdown("---")
        st.markdown("### 📥 Report Download")

        pdf_de = generate_pdf(st.session_state.pipeline_data, lang="de")
        st.download_button(
            "📄 PDF Deutsch",
            data=pdf_de,
            file_name=f"liquisto_briefing_{company_name.replace(' ', '_')}_DE.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        pdf_en = generate_pdf(st.session_state.pipeline_data, lang="en")
        st.download_button(
            "📄 PDF English",
            data=pdf_en,
            file_name=f"liquisto_briefing_{company_name.replace(' ', '_')}_EN.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.markdown("---")
    st.markdown(
        "<small>Powered by AutoGen + GPT-4</small>",
        unsafe_allow_html=True,
    )


# --- Main Area ---

st.title("🔍 Liquisto Market Intelligence")
st.caption("Multi-Agent Pipeline für B2B Sales Meeting Vorbereitung")

if start_btn:
    # Reset state and store input values
    st.session_state.running = True
    st.session_state.done = False
    st.session_state.pipeline_started = False
    st.session_state.messages = []
    st.session_state.current_agent = None
    st.session_state.pipeline_data = {}
    st.session_state.error = None
    st.session_state.input_company = company_name
    st.session_state.input_domain = web_domain
    st.rerun()

if st.session_state.running and not st.session_state.done:
    # --- Progress Section ---
    st.markdown("## Pipeline Fortschritt")

    progress_bar = st.progress(0)
    status_text = st.empty()

    # Step indicators
    step_cols = st.columns(len(PIPELINE_STEPS))
    step_placeholders = []
    for i, (agent_name, label) in enumerate(PIPELINE_STEPS):
        with step_cols[i]:
            meta = AGENT_META.get(agent_name, {})
            step_placeholders.append(st.empty())
            step_placeholders[i].markdown(
                f"<div style='text-align:center;padding:8px;border-radius:8px;"
                f"background:#f0f0f0;'>"
                f"<div style='font-size:24px'>{meta.get('icon', '⚙️')}</div>"
                f"<div style='font-size:11px;color:#666'>{label}</div></div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.markdown("## 💬 Agent-Kommunikation (Live)")
    chat_container = st.container(height=500)

    # Run pipeline in background
    def _on_message(event):
        st.session_state.messages.append(event)
        st.session_state.current_agent = event.get("agent")

    _company = st.session_state.input_company
    _domain = st.session_state.input_domain

    def _run():
        try:
            result = run_pipeline(
                company_name=_company,
                web_domain=_domain,
                on_message=_on_message,
            )
            st.session_state.pipeline_data = result["pipeline_data"]
            st.session_state.run_id = result["run_id"]
        except Exception as e:
            st.session_state.error = str(e)
        finally:
            st.session_state.done = True
            st.session_state.running = False

    # Start pipeline thread ONCE
    if not st.session_state.pipeline_started:
        st.session_state.pipeline_started = True
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    # Show current progress snapshot
    agent_order = [name for name, _ in PIPELINE_STEPS]
    msgs = st.session_state.messages
    current = st.session_state.current_agent

    if current and current in agent_order:
        idx = agent_order.index(current)
        progress_bar.progress(min((idx + 1) / len(PIPELINE_STEPS), 1.0))
        status_text.markdown(f"**Aktiver Agent:** {AGENT_META.get(current, {}).get('icon', '')} {current}")

        for i, (agent_name, label) in enumerate(PIPELINE_STEPS):
            meta = AGENT_META.get(agent_name, {})
            if i < idx:
                bg, border = "#d4edda", f"2px solid {meta.get('color', '#198754')}"
                icon_suffix = " ✅"
            elif i == idx:
                bg, border = "#fff3cd", f"2px solid {meta.get('color', '#fd7e14')}"
                icon_suffix = " ⏳"
            else:
                bg, border = "#f0f0f0", "1px solid #ddd"
                icon_suffix = ""
            step_placeholders[i].markdown(
                f"<div style='text-align:center;padding:8px;border-radius:8px;"
                f"background:{bg};border:{border}'>"
                f"<div style='font-size:24px'>{meta.get('icon', '⚙️')}{icon_suffix}</div>"
                f"<div style='font-size:11px'>{label}</div></div>",
                unsafe_allow_html=True,
            )

    # Render all messages so far
    with chat_container:
        for msg in msgs:
            agent = msg.get("agent", "?")
            meta = msg.get("meta", {})
            icon = meta.get("icon", "❓")
            color = meta.get("color", "#000")
            content = msg.get("content", "")
            ts = msg.get("timestamp", "")[:19]
            msg_type = msg.get("type", "agent_message")
            display = content[:800] + "\n... (truncated)" if len(content) > 800 else content

            if msg_type == "debug":
                bg = "#e8f4fd"
                icon = "🔧"
            elif msg_type == "error":
                bg = "#fde8e8"
                icon = "❌"
            else:
                bg = "#fafafa"

            st.markdown(
                f"<div style='border-left:3px solid {color};padding:8px 12px;"
                f"margin:4px 0;background:{bg};border-radius:4px'>"
                f"<strong>{icon} {agent}</strong> "
                f"<small style='color:#999'>{ts}</small><br>"
                f"<pre style='white-space:pre-wrap;font-size:12px;margin:4px 0 0 0'>"
                f"{display}</pre></div>",
                unsafe_allow_html=True,
            )

    # Auto-refresh every 2 seconds while running
    time.sleep(2)
    st.rerun()

elif st.session_state.done:
    # --- Results View ---
    st.success(f"✅ Pipeline abgeschlossen – Run ID: {st.session_state.run_id}")

    data = st.session_state.pipeline_data

    tab_summary, tab_company, tab_industry, tab_buyers, tab_qa, tab_chat = st.tabs([
        "📋 Briefing", "🏢 Firmenprofil", "📡 Branche", "🌐 Käufer", "🔍 Evidenz", "💬 Chat-Log"
    ])

    with tab_summary:
        synthesis = data.get("synthesis", {})
        st.markdown("### Executive Summary")
        st.write(synthesis.get("executive_summary", "Keine Daten"))

        st.markdown("### Liquisto Service-Relevanz")
        for item in synthesis.get("liquisto_service_relevance", []):
            if isinstance(item, dict):
                rel = item.get("relevance", "?")
                color_map = {"hoch": "🟢", "mittel": "🟡", "niedrig": "🔴", "unklar": "⚪"}
                dot = color_map.get(rel.lower(), "⚪")
                st.markdown(f"**{dot} {item.get('service_area', '?')}** – {rel}")
                st.caption(item.get("reasoning", ""))

        st.markdown("### Einschätzung je Option")
        for case in synthesis.get("case_assessments", []):
            if isinstance(case, dict):
                with st.expander(f"**{case.get('option', '?').upper()}** – {case.get('summary', '')}"):
                    for arg in case.get("arguments", []):
                        if isinstance(arg, dict):
                            d = arg.get("direction", "").upper()
                            icon = "✅" if d == "PRO" else "❌"
                            st.markdown(f"{icon} **{d}:** {arg.get('argument', '')}")
                            st.caption(f"Basierend auf: {arg.get('based_on', 'n/v')}")

    with tab_company:
        profile = data.get("company_profile", {})
        if profile:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Unternehmen:** {profile.get('company_name', 'n/v')}")
                st.markdown(f"**Rechtsform:** {profile.get('legal_form', 'n/v')}")
                st.markdown(f"**Gegründet:** {profile.get('founded', 'n/v')}")
                st.markdown(f"**Hauptsitz:** {profile.get('headquarters', 'n/v')}")
            with col2:
                st.markdown(f"**Branche:** {profile.get('industry', 'n/v')}")
                st.markdown(f"**Mitarbeiter:** {profile.get('employees', 'n/v')}")
                st.markdown(f"**Umsatz:** {profile.get('revenue', 'n/v')}")
                st.markdown(f"**Website:** {profile.get('website', 'n/v')}")

            products = profile.get("products_and_services", [])
            if products:
                st.markdown("**Produkte & Dienstleistungen:**")
                for p in products:
                    st.markdown(f"- {p}")
        else:
            st.info("Keine Profildaten verfügbar")

    with tab_industry:
        industry = data.get("industry_analysis", {})
        if industry:
            st.markdown(f"**Branche:** {industry.get('industry_name', 'n/v')}")
            st.markdown(f"**Marktgröße:** {industry.get('market_size', 'n/v')}")
            st.markdown(f"**Trend:** {industry.get('trend_direction', 'n/v')}")
            st.markdown(f"**Wachstum:** {industry.get('growth_rate', 'n/v')}")
            st.markdown(f"**Einschätzung:** {industry.get('assessment', 'n/v')}")
        else:
            st.info("Keine Branchendaten verfügbar")

    with tab_buyers:
        market = data.get("market_network", {})
        for tier_key, tier_label in [
            ("peer_competitors", "🏭 Peer-Konkurrenten"),
            ("downstream_buyers", "📦 Abnehmer"),
            ("service_providers", "🔧 Service-Anbieter"),
            ("cross_industry_buyers", "🔀 Cross-Industry Käufer"),
        ]:
            tier = market.get(tier_key, {})
            if isinstance(tier, dict):
                companies = tier.get("companies", [])
                with st.expander(f"{tier_label} ({len(companies)})"):
                    if tier.get("assessment"):
                        st.caption(tier["assessment"])
                    for buyer in companies:
                        if isinstance(buyer, dict):
                            st.markdown(
                                f"- **{buyer.get('name', '?')}** "
                                f"({buyer.get('city', '')}, {buyer.get('country', '')}) – "
                                f"{buyer.get('relevance', '')}"
                            )

    with tab_qa:
        qa = data.get("quality_review", {})
        if qa:
            st.markdown(f"**Evidenzqualität:** {qa.get('evidence_health', 'n/v')}")
            gaps = qa.get("open_gaps", [])
            if gaps:
                st.markdown("**Offene Lücken:**")
                for g in gaps:
                    st.warning(g)
        else:
            st.info("Keine QA-Daten verfügbar")

    with tab_chat:
        for msg in st.session_state.messages:
            agent = msg.get("agent", "?")
            meta = msg.get("meta", {})
            content = msg.get("content", "")
            ts = msg.get("timestamp", "")[:19]
            st.markdown(
                f"**{meta.get('icon', '❓')} {agent}** <small>({ts})</small>",
                unsafe_allow_html=True,
            )
            st.code(content[:2000] if len(content) > 2000 else content, language="json")

else:
    # Landing page
    st.markdown(
        """
        ### So funktioniert's

        1. **Firmenname + Domain** in der Sidebar eingeben
        2. **Pipeline starten** – 6 Agenten recherchieren automatisch
        3. **Live verfolgen** wie die Agenten kommunizieren
        4. **PDF herunterladen** (Deutsch + Englisch)

        ---

        #### Pipeline-Schritte

        | Schritt | Agent | Aufgabe |
        |---------|-------|---------|
        | 1 | 🛎️ Concierge | Intake validieren |
        | 2 | 🏢 CompanyIntelligence | Firmenprofil erstellen |
        | 3 | 📡 StrategicSignals | Branchenanalyse |
        | 4 | 🌐 MarketNetwork | 4-stufiges Käufernetzwerk |
        | 5 | 🔍 EvidenceQA | Evidenz prüfen |
        | 6 | 📋 Synthesis | Briefing mit Pro/Contra |
        """
    )
