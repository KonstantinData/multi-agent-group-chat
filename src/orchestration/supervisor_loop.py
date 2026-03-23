"""Core supervisor loop."""
from __future__ import annotations

import json
from typing import Any, Callable

from src.domain.intake import SupervisorBrief
from src.orchestration.task_router import (
    DEPARTMENT_RESEARCHERS,
    build_department_assignments,
    build_initial_assignments,
    build_synthesis_assignments,
)


MessageHook = Callable[[dict[str, Any]], None] | None

# Departments that run sequentially after each other (order matters)
_DEPARTMENT_RUN_ORDER = [
    "CompanyDepartment",
    "MarketDepartment",
    "BuyerDepartment",
    "ContactDepartment",  # depends on BuyerDepartment output
]


def emit_message(
    on_message: MessageHook,
    *,
    agent: str,
    content: str,
    message_type: str = "agent_message",
) -> dict[str, Any]:
    event = {"agent": agent, "content": content, "type": message_type}
    if on_message:
        on_message(event)
    return event


def run_supervisor_loop(
    *,
    brief: SupervisorBrief,
    run_context,
    agents: dict[str, Any],
    on_message: MessageHook = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, str]]]:
    sections: dict[str, Any] = {}
    department_packages: dict[str, Any] = {}
    messages: list[dict[str, Any]] = []
    assignments = build_initial_assignments(brief)
    department_assignments = build_department_assignments(brief)
    completed_backlog: list[dict[str, str]] = []

    # Index department assignments by department name for ordered access
    dept_assignment_map = {da.department: da for da in department_assignments}

    messages.append(
        emit_message(
            on_message,
            agent="Supervisor",
            content=agents["supervisor"].opening_message(),
        )
    )

    for assignment in assignments:
        run_context.record_task(
            assignee=assignment.assignee,
            objective=assignment.objective,
            section=assignment.target_section,
            task_key=assignment.task_key,
            model_name=assignment.model_name,
            allowed_tools=assignment.allowed_tools,
        )

    # Run departments in defined order
    for department_name in _DEPARTMENT_RUN_ORDER:
        department_assignment = dept_assignment_map.get(department_name)
        if department_assignment is None:
            continue
        if department_name not in agents.get("departments", {}):
            continue

        messages.append(
            emit_message(
                on_message,
                agent="Supervisor",
                content=json.dumps(
                    {
                        "department": department_assignment.department,
                        "status": "department_assigned",
                        "target_section": department_assignment.target_section,
                        "tasks": [
                            {
                                "task_key": a.task_key,
                                "label": a.label,
                                "objective": a.objective,
                            }
                            for a in department_assignment.assignments
                        ],
                    },
                    ensure_ascii=False,
                ),
            )
        )

        # Evaluate run_condition for Contact department
        # contact_discovery: run only when BuyerDepartment produced prioritized firms
        # contact_qualification: run only after contact_discovery completes with contacts
        # Both are modelled as a single department-level gate here; intra-department
        # ordering is left to the Lead agent.
        current_section = sections.get(department_assignment.target_section, {})
        if department_name == "ContactDepartment":
            buyer_package = department_packages.get("BuyerDepartment", {})
            buyer_candidates = buyer_package.get("accepted_points", [])
            if not buyer_candidates:
                # run_condition "buyer_department_has_prioritized_firms" not met
                # Mark all Contact tasks as skipped — no execution, no artifact
                for da in department_assignment.assignments:
                    run_context.update_task_status(task_key=da.task_key, status="skipped")
                    run_context.short_term_memory.task_statuses[da.task_key] = "skipped"
                    completed_backlog.append(
                        {
                            "task_key": da.task_key,
                            "label": da.label,
                            "target_section": da.target_section,
                            "status": "skipped",
                        }
                    )
                continue
            current_section = {**current_section, "buyer_candidates": buyer_candidates}

        department_runtime = agents["departments"][department_name]
        section_payload, department_messages, package = department_runtime.run(
            brief=brief,
            assignments=list(department_assignment.assignments),
            current_section=current_section,
            supervisor=agents["supervisor"],
            memory_store=run_context.short_term_memory,
            role_memory=run_context.retrieved_role_strategies,
            on_message=on_message,
        )
        messages.extend(department_messages)
        department_packages[department_name] = package
        sections[department_assignment.target_section] = section_payload

        acceptance = agents["supervisor"].accept_department_package(
            department=department_name,
            package=package,
        )
        messages.append(
            emit_message(
                on_message,
                agent="Supervisor",
                content=json.dumps(
                    {
                        "department": department_name,
                        "status": "department_package_reviewed",
                        **acceptance,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        status_by_task = {task["task_key"]: task["status"] for task in package.get("completed_tasks", [])}
        for assignment in department_assignment.assignments:
            task_status = status_by_task.get(assignment.task_key, "degraded")
            run_context.update_task_status(task_key=assignment.task_key, status=task_status)
            run_context.short_term_memory.task_statuses[assignment.task_key] = task_status
            completed_backlog.append(
                {
                    "task_key": assignment.task_key,
                    "label": assignment.label,
                    "target_section": assignment.target_section,
                    "status": task_status,
                }
            )

    # Strategic Synthesis Department — AG2 GroupChat
    synthesis_assignments = build_synthesis_assignments(brief)
    for assignment in synthesis_assignments:
        run_context.record_task(
            assignee=assignment.assignee,
            objective=assignment.objective,
            section=assignment.target_section,
            task_key=assignment.task_key,
            model_name=assignment.model_name,
            allowed_tools=assignment.allowed_tools,
            status="pending_synthesis",
        )

    if "synthesis" in agents:
        messages.append(
            emit_message(
                on_message,
                agent="Supervisor",
                content=json.dumps(
                    {"status": "synthesis_assigned", "department": "SynthesisDepartment"},
                    ensure_ascii=False,
                ),
            )
        )
        synthesis_result, synthesis_messages = agents["synthesis"].run(
            brief=brief,
            department_packages=department_packages,
            supervisor=agents["supervisor"],
            departments=agents["departments"],
            memory_store=run_context.short_term_memory,
            on_message=on_message,
        )
        messages.extend(synthesis_messages)
        department_packages["SynthesisDepartment"] = synthesis_result
        sections["synthesis"] = synthesis_result

        for assignment in synthesis_assignments:
            run_context.update_task_status(task_key=assignment.task_key, status="accepted")
            run_context.short_term_memory.task_statuses[assignment.task_key] = "accepted"
            completed_backlog.append(
                {
                    "task_key": assignment.task_key,
                    "label": assignment.label,
                    "target_section": assignment.target_section,
                    "status": "accepted",
                }
            )

    return sections, department_packages, messages, completed_backlog
