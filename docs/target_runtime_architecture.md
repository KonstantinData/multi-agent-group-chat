# Target Runtime Architecture

This document defines the target runtime architecture that must match
`docs/updated_runtime_architecture.drawio`.

It is intentionally written first so the intended architecture is explicit in
the repository, even if implementation work is interrupted.

## Runtime Modes

The system supports two runtime modes:

1. Initial briefing mode
2. Run-based follow-up mode

Both modes are coordinated by the `Supervisor`.

## Top-Level Roles

### Supervisor

The `Supervisor` is the single control-plane role.

Responsibilities:
- accept `company_name` and `web_domain` from the UI
- normalize the company domain and visible legal identity
- create the intake brief for the run
- translate the Liquisto standard scope into department assignments
- route assignments to the correct domain department
- track run status and formal completeness
- route follow-up questions by `run_id`

Non-responsibilities:
- no domain-level fact interpretation
- no domain-level evidence review
- no final commercial judgment

### Domain Departments

The research plane is split into four domain departments:
- `Company Department`
- `Market Department`
- `Buyer Department`
- `Contact Department`

Each department is implemented as an AutoGen-style internal group with bounded
multi-agent collaboration.

Each department contains:
- `Department Lead / Analyst`
- `Researchers`
- `Critic`
- optional `Judge`
- optional `Coding Specialist`

Department groups are responsible for:
- domain research
- domain-level interpretation
- bounded internal review loops
- a structured department package as output

The output is not raw chat. The output is a validated `Domain Package`.

### Cross-Domain Strategic Analyst

This role receives the approved domain packages from all departments and builds
the cross-domain interpretation.

Responsibilities:
- compare findings across departments
- surface tensions or contradictions
- assess the most plausible Liquisto opportunity
- derive negotiation relevance and next-step logic

### Report Writer

This role converts the approved cross-domain analysis into a professional
operator-facing report.

Responsibilities:
- executive summary
- structured report sections
- action-oriented next steps
- output shaping for PDF export in German and English

## Department Model

Each department operates as a bounded collaborative group.

### Company Department

Questions owned:
- who the target company is
- what it sells or makes
- which goods, materials, spare parts, or inventory positions are visible
- which items are made by the company, distributed/resold, or held in stock
- which public signals suggest economic or commercial pressure

The `CompanyLead` owns the goods classification. The Researcher delivers raw
evidence about visible products and assets, but the Lead applies the
classification frame (`made_vs_distributed_vs_held_in_stock`) and writes the
final classification into the department package. This is a domain judgment,
not a research task.

### Market Department

Questions owned:
- market situation, demand, and supply pressure
- overcapacity or contraction signals
- repurposing and circularity paths
- analytics and operational improvement signals

### Buyer Department

Questions owned:
- peer companies
- plausible buyers
- resale, redeployment, reuse, or secondary-market paths
- likely downstream, service, broker, distributor, or cross-industry routes

### Contact Department

Questions owned:
- decision-maker contacts at prioritized buyer firms
- procurement leads, COO/VP operations, asset management contacts
- seniority and function classification per contact
- outreach angles per contact based on Liquisto's business model

The Contact Department runs after the Buyer Department. It reads
`buyer_candidates` from the approved `market_network` package and builds
contact queries per firm. If no buyer candidates are available, the department
falls back to industry-scoped contact discovery.

Output section: `contact_intelligence`.

## AutoGen Department Groups

Each department is implemented as a real AG2 GroupChat, not as a single
generic worker or a Python orchestration loop.

### Group structure

Each department group consists of five `ConversableAgent` instances:

| Role                      | LLM          | Registered tool                                   |
| ------------------------- | ------------ | ------------------------------------------------- |
| Department Lead / Analyst | gpt-4.1      | `request_supervisor_revision`, `finalize_package` |
| Researcher                | gpt-4.1-mini | `run_research`                                    |
| Critic                    | gpt-4.1      | `review_research`                                 |
| Judge                     | gpt-4.1      | `judge_decision`                                  |
| Coding Specialist         | gpt-4.1-mini | `suggest_refined_queries`                         |

### Conversation mechanics

- The Lead initiates the chat via `initiate_chat` with the investigation plan
- `GroupChatManager` with a custom `speaker_selection_method` (state-machine
  selector) routes turns based on workflow phase and tool-call state
- The Lead explicitly addresses the next agent in every message
- Tools are Python closures registered per agent via `register_function`
- The chat terminates when the Lead calls `finalize_package`, which returns `TERMINATE`

### Intra-group escalation path

```text
Lead → Researcher: run_research(task_key)
Researcher → [group]: reports findings
Lead → Critic: review_research(task_key)
Critic → [group]: approved / rejected
  if rejected:
    Lead calls: request_supervisor_revision(task_key)
      → retry=true, authorize_coding_specialist=true:
          Lead → CodingSpecialist: suggest_refined_queries(task_key)
          Lead → Researcher: run_research(task_key) [with refined queries]
      → retry=true, authorize_coding_specialist=false:
          Lead → Researcher: run_research(task_key) [with revision request]
      → retry=false:
          Lead → Judge: judge_decision(task_key)
          Lead proceeds to next task
Lead calls: finalize_package(summary) → TERMINATE
```

### Supervisor boundary

The Supervisor passes itself as a reference to `DepartmentLeadAgent.run()`.
The Lead calls `supervisor.decide_revision()` directly as a tool side-effect.
There is no AG2 message passing between the Supervisor layer and the
department group — the boundary is a Python method call, not a chat turn.

### Implementation requirements

- fixed role profiles per department (CompanyLead, MarketLead, BuyerLead, ContactLead)
- max_round = number of assignments × 15 (hard cap)
- termination via `finalize_package` returning `TERMINATE` in message content
- structured `DepartmentPackage` output, not a raw chat log
- fallback package assembled from available partial results if max_round is hit

## Memory Model

### Run-Level Short-Term Memory

The run keeps a global short-term memory containing:
- intake brief
- task statuses
- department packages
- approved section outputs
- review results
- synthesis results
- report artifacts

### Department Working Memory

Each department keeps a working-memory view for the active run.

It contains:
- assignment-specific evidence
- internal review notes
- open questions
- accepted and rejected points
- department package drafts

### Department Strategy Memory

Long-term memory is department-specific and stores reusable working patterns,
not company facts.

It stores:
- effective query patterns
- useful review heuristics
- reusable packaging patterns
- follow-up answer patterns

It must not store:
- unverified company facts
- stale company-specific claims as permanent truth

## Follow-Up Mode

Follow-up mode starts from a stored `run_id`.

Flow:
1. user enters `run_id` and a question in the UI
2. the system resolves the historical run context
3. the `Supervisor` routes the question to the correct department or to the
   cross-domain layer
4. the responsible unit answers from stored run memory first
5. the follow-up result is stored as a follow-up artifact

Follow-up mode requires:
- persisted run context
- persisted department packages
- separate follow-up session memory
- explicit run-to-follow-up linkage via `run_id`

## Required Output Artifacts

Each run must produce:
- `pipeline_data.json`
- `run_context.json`
- `memory_snapshot.json`
- domain package data in the run context
- follow-up artifacts when follow-up answers are generated
- PDF export in German and English on demand

## Replaced Architecture Elements

The target architecture replaces:
- separate intake and interpretation side roles with a supervisor-led control plane
- a flat worker layer with explicit department groups
- supervisor-owned domain quality judgments with department-owned review
