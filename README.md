# Liquisto Department Runtime

Multi-agent intelligence pipeline that builds Liquisto pre-meeting briefings.
The system takes `company_name` and `web_domain` as input and produces a
structured research briefing with company analysis, market context, buyer
landscape, contact intelligence, strategic synthesis, and an operator-facing
report.

Built on [AG2 (AutoGen)](https://github.com/ag2ai/ag2) group chats with
bounded department collaboration, coordinated by a single Supervisor.

## Quickstart

```bash
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Unix

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set OpenAI API key
echo OPENAI_API_KEY=sk-... > .env

# 4. Validate environment
python preflight.py

# 5. Start the UI
streamlit run ui/app.py
```

## Architecture

Architecture spec: [docs/target_runtime_architecture.md](docs/target_runtime_architecture.md) ·
Diagram: [docs/updated_runtime_architecture.drawio](docs/updated_runtime_architecture.drawio)

### Control Plane

- **Supervisor** — intake normalization, domain routing, run coordination, follow-up routing.
  No domain-level fact interpretation or evidence review.

### Research Plane

Four domain departments, each implemented as a bounded AG2 GroupChat:

| Department | Scope |
|------------|-------|
| Company Department | Company fundamentals, economic/commercial situation, product and asset scope |
| Market Department | Market situation, repurposing/circularity, analytics and operational improvement signals |
| Buyer Department | Peer companies, monetization and redeployment paths |
| Contact Department | Contact discovery and qualification at prioritized buyer firms |

Each department group contains:

| Role | Model | Tool |
|------|-------|------|
| Lead / Analyst | gpt-4.1 | `finalize_package`, `request_supervisor_revision` |
| Researcher | gpt-4.1-mini | `run_research` |
| Critic | gpt-4.1 | `review_research` |
| Judge (optional) | gpt-4.1 | `judge_decision` |
| Coding Specialist (optional) | gpt-4.1-mini | `suggest_refined_queries` |

### Synthesis Plane

- **Synthesis Department** — AG2 group that builds the cross-domain Liquisto opportunity view from all approved department packages.
- **Report Writer** — turns the approved analysis into a professional operator-facing report for PDF export (German + English).

## Runtime Modes

### Initial briefing

1. Supervisor normalizes intake → `SupervisorBrief`
2. Task router builds assignments from the standard Liquisto scope
3. Departments run sequentially: Company → Market → Buyer → Contact
4. Each department returns a validated `DepartmentPackage`
5. Synthesis Department builds the cross-domain interpretation
6. Report Writer produces the operator-facing report package
7. Artifacts exported to `artifacts/runs/<run_id>/`

### Follow-up

1. User enters `run_id` and a question in the UI
2. System loads the historical run context
3. Supervisor routes the question to the correct department or synthesis layer
4. Answer is generated from stored run memory and persisted as a follow-up artifact

## Key Files

| File | Purpose |
|------|---------|
| [src/pipeline_runner.py](src/pipeline_runner.py) | Public runtime entrypoint for UI and CLI |
| [src/orchestration/supervisor_loop.py](src/orchestration/supervisor_loop.py) | Supervisor-controlled department routing loop |
| [src/orchestration/department_runtime.py](src/orchestration/department_runtime.py) | Bounded department group runtime |
| [src/orchestration/synthesis_runtime.py](src/orchestration/synthesis_runtime.py) | Synthesis department AG2 runtime |
| [src/orchestration/task_router.py](src/orchestration/task_router.py) | Supervisor mandate → department assignments |
| [src/orchestration/follow_up.py](src/orchestration/follow_up.py) | Run loading, routing, persisted follow-up answers |
| [src/agents/definitions.py](src/agents/definitions.py) | Agent specs and runtime agent factory |
| [src/app/use_cases.py](src/app/use_cases.py) | Liquisto standard scope and task backlog |
| [src/config/settings.py](src/config/settings.py) | Model selection, role defaults, API key resolution |
| [src/exporters/pdf_report.py](src/exporters/pdf_report.py) | PDF report generation (DE + EN) |
| [ui/app.py](ui/app.py) | Streamlit UI |

## Memory

### Short-term (per run)

Stored under `artifacts/runs/<run_id>/`. Contains:
supervisor brief, task statuses, department packages, conversation traces,
validated pipeline data, report package, follow-up history.

### Long-term (cross-run)

Stored at `artifacts/memory/long_term_memory.json`. Contains reusable strategy
patterns — query patterns, review heuristics, packaging patterns. Never stores
unverified company facts.

## Output Artifacts

Each run writes to `artifacts/runs/<run_id>/`:

| File | Content |
|------|---------|
| `run_meta.json` | Run metadata (company, domain, status, timing) |
| `chat_history.json` | Full message trace |
| `pipeline_data.json` | Structured research output |
| `run_context.json` | Supervisor brief, task statuses, department packages |
| `memory_snapshot.json` | Short-term memory snapshot |
| `follow_up_history.json` | Follow-up Q&A (when applicable) |

## UI

The Streamlit UI supports:
- Starting a fresh run with company name and web domain
- Live progress tracking across all pipeline steps
- Loading an existing run by `run_id`
- Viewing department packages with report segments
- Viewing cross-domain synthesis and report package
- Asking follow-up questions routed to the correct department
- Downloading German and English PDF briefings

## Configuration

- **API key**: set `OPENAI_API_KEY` in `.env` or as environment variable
- **Model overrides**: `OPENAI_MODEL_<ROLE>` and `OPENAI_STRUCTURED_MODEL_<ROLE>` env vars
- **Defaults**: defined in `src/config/settings.py` → `ROLE_MODEL_DEFAULTS`
- **Streamlit**: `.streamlit/config.toml`

## Validation

```bash
python preflight.py   # environment, packages, project files, API key, import chain, port
pytest                # unit tests
```
