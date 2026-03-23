"""Translate the supervisor mandate into department assignments."""
from __future__ import annotations

from dataclasses import dataclass

from src.app.use_cases import build_standard_backlog
from src.config import get_role_model_selection
from src.domain.intake import SupervisorBrief
from src.orchestration.tool_policy import resolve_allowed_tools


DEPARTMENT_RESEARCHERS = {
    "CompanyDepartment": "CompanyResearcher",
    "MarketDepartment": "MarketResearcher",
    "BuyerDepartment": "BuyerResearcher",
    "ContactDepartment": "ContactResearcher",
}


@dataclass(frozen=True, slots=True)
class Assignment:
    task_key: str
    assignee: str
    target_section: str
    label: str
    objective: str
    model_name: str
    allowed_tools: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DepartmentAssignment:
    department: str
    target_section: str
    assignments: tuple[Assignment, ...]


def _assignment_role_name(assignee: str) -> str:
    return DEPARTMENT_RESEARCHERS.get(assignee, assignee)


def build_initial_assignments(brief: SupervisorBrief) -> list[Assignment]:
    assignments: list[Assignment] = []
    for item in build_standard_backlog():
        assignee = str(item["assignee"])
        role_name = _assignment_role_name(assignee)
        allowed_tools = resolve_allowed_tools(role_name, str(item["task_key"]))
        chat_model, structured_model = get_role_model_selection(role_name)
        assignments.append(
            Assignment(
                task_key=str(item["task_key"]),
                assignee=assignee,
                target_section=str(item["target_section"]),
                label=str(item["label"]),
                objective=str(item["objective_template"]).format(
                    company_name=brief.company_name,
                    industry_hint=brief.industry_hint if brief.industry_hint != "n/v" else brief.company_name,
                ),
                model_name=structured_model if "llm_structured" in allowed_tools else chat_model,
                allowed_tools=allowed_tools,
            )
        )
    return assignments


def build_department_assignments(brief: SupervisorBrief) -> list[DepartmentAssignment]:
    grouped: dict[tuple[str, str], list[Assignment]] = {}
    for assignment in build_initial_assignments(brief):
        if assignment.assignee not in DEPARTMENT_RESEARCHERS:
            continue
        key = (assignment.assignee, assignment.target_section)
        grouped.setdefault(key, []).append(assignment)
    return [
        DepartmentAssignment(
            department=department,
            target_section=target_section,
            assignments=tuple(grouped[(department, target_section)]),
        )
        for department, target_section in grouped
    ]


def build_synthesis_assignments(brief: SupervisorBrief) -> list[Assignment]:
    return [
        assignment
        for assignment in build_initial_assignments(brief)
        if assignment.assignee == "SynthesisDepartment"
    ]
