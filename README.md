# Liquisto Department Runtime

This repository implements the target runtime architecture described in
[docs/updated_runtime_architecture.drawio](/Users/konstantinmac/Documents/repositories/multi-agent-group-chat/docs/updated_runtime_architecture.drawio)
and specified in
[docs/target_runtime_architecture.md](/Users/konstantinmac/Documents/repositories/multi-agent-group-chat/docs/target_runtime_architecture.md).

The system builds a Liquisto pre-meeting briefing from:
- `company_name`
- `web_domain`

It also supports run-based follow-up questions through `run_id`.

## Architecture

### Control Plane

- `Supervisor`
  Owns intake normalization, domain routing, run coordination, and follow-up routing.

### Research Plane

- `Company Department`
  Owns company fundamentals, economic and commercial situation, and product and asset scope.
- `Market Department`
  Owns market situation, repurposing and circularity, and analytics or operational improvement signals.
- `Buyer Department`
  Owns peer companies plus monetization and redeployment paths.

Each department is implemented as a bounded AutoGen-style group with:
- `Lead`
- `Researcher`
- `Critic`
- optional `Judge`
- optional `Coding Specialist`

### Synthesis Plane

- `CrossDomainStrategicAnalyst`
  Builds the Liquisto interpretation from approved department packages.
- `ReportWriter`
  Turns the approved analysis into a professional report structure for PDF export.

## Runtime Modes

### Initial briefing mode

1. The `Supervisor` normalizes intake and prepares the run brief.
2. The `Supervisor` routes work to the three domain departments.
3. Each department runs bounded internal collaboration and returns an approved `Domain Package`.
4. The `CrossDomainStrategicAnalyst` builds the Liquisto opportunity view.
5. The `ReportWriter` prepares the operator-facing report package.

### Follow-up mode

1. A user enters `run_id` and a question in the UI.
2. The system loads the historical run context.
3. The `Supervisor` routes the question to the correct department or to the cross-domain layer.
4. The answer is generated from stored run memory first and then persisted as a follow-up artifact.

## Key Files

- [src/pipeline_runner.py](/Users/konstantinmac/Documents/repositories/multi-agent-group-chat/src/pipeline_runner.py)
  Public runtime entrypoint for UI and CLI.
- [src/orchestration/supervisor_loop.py](/Users/konstantinmac/Documents/repositories/multi-agent-group-chat/src/orchestration/supervisor_loop.py)
  Supervisor-controlled department routing loop.
- [src/orchestration/department_runtime.py](/Users/konstantinmac/Documents/repositories/multi-agent-group-chat/src/orchestration/department_runtime.py)
  Bounded department group runtime with AutoGen group metadata.
- [src/orchestration/follow_up.py](/Users/konstantinmac/Documents/repositories/multi-agent-group-chat/src/orchestration/follow_up.py)
  Run loading, routing, and persisted follow-up answers.
- [src/app/use_cases.py](/Users/konstantinmac/Documents/repositories/multi-agent-group-chat/src/app/use_cases.py)
  Liquisto standard scope and task backlog.
- [ui/app.py](/Users/konstantinmac/Documents/repositories/multi-agent-group-chat/ui/app.py)
  Streamlit UI for initial runs, department packages, report view, and follow-up mode.

## Memory

Run artifacts persist:
- supervisor brief
- task statuses
- department packages
- department conversation traces
- validated pipeline data
- report package
- follow-up history

Short-term memory is stored per run under `artifacts/runs/<run_id>/`.

Long-term memory stores reusable strategies, not company facts:
- query patterns
- review thresholds
- packaging heuristics
- follow-up answer patterns

## Output Artifacts

Each run writes:
- `run_meta.json`
- `chat_history.json`
- `pipeline_data.json`
- `run_context.json`
- `memory_snapshot.json`

Follow-up mode additionally writes:
- `follow_up_history.json`

## UI

The Streamlit UI now supports:
- starting a fresh run
- loading an existing run by `run_id`
- viewing department packages
- viewing cross-domain synthesis and report package
- asking follow-up questions against a stored run
- downloading German and English PDFs

## Validation

Use the repository virtual environment:

```bash
.venv/bin/python preflight.py
.venv/bin/pytest
```
