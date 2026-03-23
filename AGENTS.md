# Repository Instructions

## Project Overview

Liquisto Department Runtime — a multi-agent intelligence pipeline that builds
pre-meeting briefings from `company_name` and `web_domain`. The system uses
AG2 (AutoGen) group chats inside bounded domain departments, coordinated by a
single Supervisor control plane.

## Python Environment

- Virtual environment at `.venv`.
- Run commands with `.venv/bin/python` (Unix) or `.venv\Scripts\python` (Windows).
- Run tests with `.venv/bin/pytest` or `.venv\Scripts\pytest`.
- Dependencies in `requirements.txt` — key packages: `ag2`, `openai`, `pydantic`, `streamlit`, `reportlab`, `python-dotenv`.
- Never assume globally installed `python`, `pytest`, or packages point to the repo environment.

## Validation

```bash
.venv/bin/python preflight.py   # full environment and import chain check
.venv/bin/pytest                # unit tests
```

## Architecture

### Three Planes

1. **Control Plane** — `Supervisor` (`src/agents/supervisor.py`)
   Intake normalization, domain routing, run coordination, follow-up routing.
   No domain-level fact interpretation or evidence review.

2. **Research Plane** — four domain departments, each an AG2 GroupChat:
   - `CompanyDepartment` → company fundamentals, economic signals, product/asset scope
   - `MarketDepartment` → market situation, repurposing/circularity, analytics signals
   - `BuyerDepartment` → peer companies, monetization/redeployment paths
   - `ContactDepartment` → contact discovery at prioritized buyer firms (depends on BuyerDepartment output)

3. **Synthesis Plane**
   - `SynthesisDepartment` (`src/orchestration/synthesis_runtime.py`) — cross-domain strategic analysis via AG2 group
   - `ReportWriter` (`src/agents/report_writer.py`) — operator-facing report for PDF export

### Department Group Structure

Each department is a bounded AG2 GroupChat with five `ConversableAgent` roles:

| Role               | Model        | Tool                          |
|--------------------|--------------|-------------------------------|
| Lead / Analyst     | gpt-4.1      | `finalize_package`, `request_supervisor_revision` |
| Researcher         | gpt-4.1-mini | `run_research`                |
| Critic             | gpt-4.1      | `review_research`             |
| Judge (optional)   | gpt-4.1      | `judge_decision`              |
| Coding Specialist  | gpt-4.1-mini | `suggest_refined_queries`     |

Orchestration: `DepartmentRuntime` (`src/orchestration/department_runtime.py`) wraps
`DepartmentLeadAgent` (`src/agents/lead.py`). The Lead initiates the AG2 chat,
`GroupChatManager` with `speaker_selection_method="auto"` routes turns, and the
chat terminates when the Lead calls `finalize_package` → `TERMINATE`.

### Supervisor ↔ Department Boundary

The Supervisor is passed as a reference to `DepartmentLeadAgent.run()`.
The Lead calls `supervisor.decide_revision()` as a Python method call — not an
AG2 message. There is no chat-level message passing across this boundary.

## Key File Map

| File | Purpose |
|------|---------|
| `src/pipeline_runner.py` | Public runtime entrypoint (UI + CLI) |
| `src/orchestration/supervisor_loop.py` | Supervisor-controlled department routing loop |
| `src/orchestration/department_runtime.py` | Bounded department group runtime |
| `src/orchestration/synthesis_runtime.py` | Synthesis department AG2 runtime |
| `src/orchestration/task_router.py` | Translates supervisor mandate into department assignments |
| `src/orchestration/follow_up.py` | Run loading, routing, persisted follow-up answers |
| `src/orchestration/tool_policy.py` | Per-role tool allow-lists |
| `src/agents/definitions.py` | Agent specs and `create_runtime_agents()` factory |
| `src/agents/lead.py` | `DepartmentLeadAgent` — owns the AG2 group lifecycle |
| `src/agents/supervisor.py` | `SupervisorAgent` |
| `src/agents/worker.py` | Generic researcher agent |
| `src/agents/critic.py` | Critic agent |
| `src/agents/judge.py` | Judge agent |
| `src/agents/coding_assistant.py` | Coding specialist agent |
| `src/agents/strategic_analyst.py` | Cross-domain strategic analyst |
| `src/agents/report_writer.py` | Report writer agent |
| `src/agents/synthesis_department.py` | Synthesis department AG2 group agent |
| `src/app/use_cases.py` | Liquisto standard scope + task backlog |
| `src/config/settings.py` | Model selection, role-model defaults, API key resolution |
| `src/domain/intake.py` | `IntakeRequest`, `SupervisorBrief` |
| `src/models/schemas.py` | Pydantic schemas and `empty_pipeline_data()` |
| `src/memory/short_term_store.py` | Run-level short-term memory |
| `src/memory/long_term_store.py` | File-backed long-term strategy memory |
| `src/memory/consolidation.py` | Post-run role pattern consolidation |
| `src/memory/retrieval.py` | Strategy retrieval for run priming |
| `src/research/` | Search, fetch, extract, normalize, source scoring |
| `src/tools/research.py` | Research tool implementations |
| `src/exporters/json_export.py` | Run artifact JSON export |
| `src/exporters/pdf_report.py` | PDF report generation (DE + EN) |
| `ui/app.py` | Streamlit UI |
| `preflight.py` | Environment validation script |

## Runtime Flow (Initial Briefing)

1. `Supervisor` normalizes intake → `SupervisorBrief`
2. `task_router` builds assignments from `STANDARD_TASK_BACKLOG`
3. Departments run sequentially: Company → Market → Buyer → Contact
4. Each department returns a validated `DepartmentPackage` (not raw chat)
5. `SynthesisDepartment` builds cross-domain interpretation from all packages
6. `ReportWriter` produces the operator-facing report package
7. Artifacts exported to `artifacts/runs/<run_id>/`

Department run order is fixed in `supervisor_loop._DEPARTMENT_RUN_ORDER`.
ContactDepartment receives BuyerDepartment output as context.

## Memory Model

- **Short-term** (`ShortTermMemoryStore`): per-run facts, sources, task outputs, critic reviews, department packages, usage totals. Isolated department workspaces via `open_department_workspace()`.
- **Long-term** (`FileLongTermMemoryStore`): reusable strategy patterns across runs — query patterns, review heuristics, packaging patterns. Never stores unverified company facts.
- **Consolidation**: `consolidate_role_patterns()` extracts role-specific patterns after a run; stored only if `should_store_strategy()` passes.

## Output Artifacts

Each run writes to `artifacts/runs/<run_id>/`:
- `run_meta.json`, `chat_history.json`, `pipeline_data.json`, `run_context.json`, `memory_snapshot.json`
- Follow-up mode adds `follow_up_history.json`

## Configuration

- OpenAI API key: `.env` file or `OPENAI_API_KEY` env var
- Model overrides per role: `OPENAI_MODEL_<ROLE>` and `OPENAI_STRUCTURED_MODEL_<ROLE>` env vars
- Default models defined in `src/config/settings.py` → `ROLE_MODEL_DEFAULTS`
- Streamlit config in `.streamlit/config.toml`

## Development Conventions

- All domain types live in `src/domain/` — keep them as plain dataclasses or Pydantic models.
- Agent implementations in `src/agents/` — each file owns one agent role.
- Orchestration logic in `src/orchestration/` — never put domain interpretation here.
- Tools are Python closures registered per agent via `register_function`, not global singletons.
- Department output is always a structured `DepartmentPackage`, never raw chat logs.
- `max_round` per department = number of assignments × 15 (hard cap).
- Termination via `finalize_package` returning `TERMINATE` in message content.
- Fallback package assembled from partial results if `max_round` is hit.
- Keep `src/app/use_cases.py` as the single source of truth for the Liquisto research scope.
- Pipeline steps defined in `pipeline_runner.PIPELINE_STEPS` — update when adding departments.

## Testing

- Test files at repo root: `test_pipeline.py`, `test_preflight.py`, `test_startup.py`.
- Run with `.venv/bin/pytest` from repo root.
- `preflight.py` validates environment, packages, project files, API key, import chain, and port availability.
