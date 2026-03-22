# Development Checklist

Status: aligned with the implemented target runtime.

## Architecture

- [x] `Supervisor` owns intake normalization and routing
- [x] three explicit domain departments are the research plane
- [x] departments are implemented as real AG2 GroupChats (ConversableAgents + GroupChatManager)
- [x] domain quality judgment stays inside departments
- [x] cross-domain synthesis is separate from the supervisor
- [x] report writing is separate from cross-domain synthesis
- [x] run-based follow-up is routed by `run_id`

## Runtime Data

- [x] supervisor brief is persisted in the run context
- [x] department packages are persisted in short-term memory
- [x] department conversation traces are persisted in short-term memory
- [x] report package is persisted in the run context
- [x] follow-up answers are persisted as run artifacts

## UI

- [x] initial run flow uses the new supervisor-led intake
- [x] department packages are visible in the UI
- [x] synthesis and report package are visible in the UI
- [x] follow-up questions can be asked by `run_id`
- [x] German and English PDF downloads remain available

## Cleanup

- [x] deprecated runtime paths removed
- [x] deprecated interpretation path removed
- [x] deprecated helper modules removed
- [x] unused intermediate memory helper removed
- [x] unused prompt stub removed

## Validation

- [x] `.venv/bin/pytest`
- [x] `.venv/bin/python preflight.py`
- [x] `xmllint --noout docs/runtime_architecture.drawio docs/updated_runtime_architecture.drawio docs/company_department_run.drawio`
