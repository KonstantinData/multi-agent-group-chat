"""Liquisto Runtime Architecture UI."""
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

st.set_page_config(page_title="Liquisto Runtime", page_icon="📄", layout="wide")


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
    return sorted([path for path in RUNS_DIR.iterdir() if path.is_dir()], key=lambda item: item.name, reverse=True)


def _load_run(run_id: str) -> None:
    artifact = load_run_artifact(run_id)
    run_context = artifact["run_context"]
    pipeline_data = artifact["pipeline_data"]
    history_path = artifact["run_dir"] / "chat_history.json"
    messages = []
    if history_path.exists():
        raw_messages = json.loads(history_path.read_text(encoding="utf-8"))
        messages = [
            {
                "agent": item.get("name", "Agent"),
                "content": item.get("content", ""),
                "type": "agent_message",
            }
            for item in raw_messages
        ]
    st.session_state.running = False
    st.session_state.done = True
    st.session_state.pipeline_started = False
    st.session_state.messages = messages
    st.session_state.pipeline_data = pipeline_data
    st.session_state.run_context = run_context
    st.session_state.run_id = run_id
    st.session_state.status = run_context.get("status")
    st.session_state.error = None
    st.session_state.worker_queue = None
    st.session_state.loaded_notice = run_id


def _message_preview(content: str, limit: int = 140) -> str:
    text = str(content or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text or "(empty)"
    return text[:limit].rstrip() + "..."


def _parse_payload(message: dict) -> dict | None:
    content = message.get("content", "")
    if not isinstance(content, str):
        return None
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _step_progress() -> tuple[int, str]:
    if not st.session_state.messages:
        return 0, "Waiting to start"
    current_step = 1
    current_label = "Supervisor intake and routing"
    for message in st.session_state.messages:
        agent = message.get("agent", "")
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


def _task_rows() -> list[dict[str, str]]:
    statuses = st.session_state.run_context.get("short_term_memory", {}).get("task_statuses", {})
    return [
        {
            "label": item["label"],
            "assignee": item["assignee"],
            "status": statuses.get(item["task_key"], "pending"),
        }
        for item in BACKLOG
    ]


def _department_packages() -> dict[str, dict]:
    return st.session_state.run_context.get("short_term_memory", {}).get("department_packages", {})


def _render_message_feed() -> None:
    for message in reversed(st.session_state.messages[-40:]):
        agent = message.get("agent", "Agent")
        content = message.get("content", "")
        meta = AGENT_META.get(agent, {"summary": "", "icon": "[]"})
        title = f"{meta.get('icon', '[]')} {agent} - {_message_preview(content)}"
        with st.expander(title, expanded=False):
            st.code(content[:12000], language="json")


def _render_department_packages() -> None:
    packages = _department_packages()
    if not packages:
        st.info("No department packages available yet.")
        return
    for department in ["CompanyDepartment", "MarketDepartment", "BuyerDepartment", "ContactDepartment"]:
        package = packages.get(department)
        if not package:
            continue
        with st.container(border=True):
            st.subheader(department.replace("Department", " Department"))

            # Report segment narrative (new)
            segment = package.get("report_segment", {})
            if segment and segment.get("narrative_summary", "n/v") != "n/v":
                confidence_color = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(segment.get("confidence", "low"), "⚪")
                st.markdown(f"**Report segment** {confidence_color} _{segment.get('confidence', 'n/v')} confidence_")
                st.write(segment.get("narrative_summary", ""))
                if segment.get("key_findings"):
                    with st.expander("Key findings"):
                        for item in segment["key_findings"]:
                            st.write(f"- {item}")
            else:
                st.caption(package.get("summary", "n/v"))

            # Contact Intelligence: show contacts table
            if department == "ContactDepartment":
                contact_section = st.session_state.pipeline_data.get("contact_intelligence", {})
                contacts = contact_section.get("prioritized_contacts") or contact_section.get("contacts", [])
                if contacts:
                    st.write(f"**Prioritized contacts** ({len(contacts)} found)")
                    for c in contacts:
                        with st.expander(f"{c.get('name', 'n/v')} — {c.get('rolle_titel', 'n/v')} @ {c.get('firma', 'n/v')}"):
                            st.write(f"**Funktion:** {c.get('funktion', 'n/v')}")
                            st.write(f"**Seniorität:** {c.get('senioritaet', 'n/v')}")
                            st.write(f"**Confidence:** {c.get('confidence', 'n/v')}")
                            st.write(f"**Relevanz:** {c.get('relevance_reason', 'n/v')}")
                            st.info(f"**Outreach-Angle:** {c.get('suggested_outreach_angle', 'n/v')}")
                else:
                    st.caption("No contacts found yet.")
                continue

            autogen_group = package.get("autogen_group", {})
            st.write("AutoGen group:", ", ".join(autogen_group.get("members", [])) or "n/v")
            col_a, col_b = st.columns(2)
            with col_a:
                st.write("Visual focus")
                for item in package.get("visual_focus", []):
                    st.write(f"- {item}")
            with col_b:
                st.write("Open questions")
                if package.get("open_questions"):
                    for item in package.get("open_questions", []):
                        st.write(f"- {item}")
                else:
                    st.write("- none")
            st.json(package.get("section_payload", {}))


def _render_report_panel() -> None:
    pipeline_data = st.session_state.pipeline_data
    report_package = st.session_state.run_context.get("report_package", {})
    synthesis = pipeline_data.get("synthesis", {})
    quality = pipeline_data.get("quality_review", {})
    st.subheader("Cross-domain synthesis")
    st.write(synthesis.get("executive_summary", "n/v"))
    st.write("Opportunity assessment:", synthesis.get("opportunity_assessment_summary", "n/v"))
    if synthesis.get("next_steps"):
        st.write("Next steps")
        for item in synthesis["next_steps"]:
            st.write(f"- {item}")
    st.subheader("Report package")
    st.json(report_package or {"report_status": "n/v"})
    st.subheader("Quality review")
    st.json(quality or {})


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

with st.sidebar:
    st.header("Initial Run")
    company_name = st.text_input("Company name", value=st.session_state.get("input_company", ""))
    web_domain = st.text_input("Web domain", value=st.session_state.get("input_domain", ""))
    if st.button("Start run", disabled=st.session_state.running or not company_name or not web_domain, use_container_width=True):
        _start_pipeline(company_name, web_domain)
        st.rerun()

    st.divider()
    run_dirs = _run_dirs()
    run_options = [path.name for path in run_dirs[:30]]
    selected_run = st.selectbox("Load run", options=[""] + run_options, index=0)
    if st.button("Load selected run", disabled=st.session_state.running or not selected_run, use_container_width=True):
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


st.title("Liquisto Department Runtime")
st.caption("Supervisor-led intake, department groups, cross-domain synthesis, and run-based follow-up")

if st.session_state.running and not st.session_state.done:
    current_step, current_label = _step_progress()
    progress = current_step / len(PIPELINE_STEPS)
    st.progress(progress)
    st.write(current_label)

    cols = st.columns(len(PIPELINE_STEPS))
    for index, (agent_name, label) in enumerate(PIPELINE_STEPS):
        meta = AGENT_META.get(agent_name, {"icon": "[]", "color": "#d0d5dd"})
        active = index + 1 <= current_step
        background = meta["color"] if active else "#f2f4f7"
        text_color = "#ffffff" if active else "#101828"
        cols[index].markdown(
            f"""
            <div style="border:1px solid #d0d5dd;border-radius:14px;padding:12px;background:{background};min-height:110px;">
              <div style="font-size:26px;color:{text_color};">{meta['icon']}</div>
              <div style="font-weight:700;color:{text_color};margin-top:8px;">{label}</div>
              <div style="font-size:12px;color:{text_color};opacity:0.92;">{agent_name}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    worker_queue = st.session_state.worker_queue
    _company_name = st.session_state.get("input_company", "")
    _web_domain = st.session_state.get("input_domain", "")

    def _on_message(event: dict) -> None:
        worker_queue.put({"event": "message", "payload": event})

    def _run() -> None:
        try:
            result = run_pipeline(
                company_name=_company_name,
                web_domain=_web_domain,
                on_message=_on_message,
            )
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

if st.session_state.error:
    st.error(st.session_state.error)

if st.session_state.done and st.session_state.run_id:
    if st.session_state.status == "completed":
        st.success(f"Run completed: {st.session_state.run_id}")
    elif st.session_state.status == "completed_but_not_usable":
        st.warning(f"Run completed with remaining gaps: {st.session_state.run_id}")
    elif st.session_state.loaded_notice == st.session_state.run_id:
        st.info(f"Loaded run: {st.session_state.run_id}")

    summary_cols = st.columns(4)
    summary_cols[0].metric("Run ID", st.session_state.run_id)
    summary_cols[1].metric("Status", st.session_state.status or "n/v")
    summary_cols[2].metric(
        "Readiness score",
        str(st.session_state.pipeline_data.get("research_readiness", {}).get("score", "n/v")),
    )
    summary_cols[3].metric(
        "Estimated cost (USD)",
        f"{st.session_state.budget.get('estimated_cost_usd', 0.0):.4f}",
    )

    tab_overview, tab_departments, tab_report, tab_follow_up, tab_messages = st.tabs(
        ["Overview", "Departments", "Report", "Follow-up", "Messages"]
    )

    with tab_overview:
        st.subheader("Task backlog")
        for row in _task_rows():
            st.write(f"- {row['label']} | {row['assignee']} | {row['status']}")
        st.subheader("Company summary")
        st.json(st.session_state.pipeline_data.get("company_profile", {}))

    with tab_departments:
        _render_department_packages()

    with tab_report:
        _render_report_panel()

    with tab_follow_up:
        _render_follow_up_panel()

    with tab_messages:
        _render_message_feed()
