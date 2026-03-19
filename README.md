# Liquisto Market Intelligence Pipeline

AutoGen-based multi-agent group chat for B2B sales meeting preparation.

## Purpose

Prepare Liquisto sales team for meetings with potential customers by researching the intake company and identifying buyer markets for their products.

**Input:** Company Name + Web Domain  
**Output:** Comprehensive briefing with company profile, industry analysis, 4-tier buyer network, and transparent pro/contra assessment for each Liquisto option.

## Liquisto Service Areas

1. **Excess Inventory** – One-stop platform for surplus optimization
2. **Repurposing** – Collaborative ideation for unused materials
3. **Analytics** – Value chain analytics as a service

The pipeline determines which areas might be relevant based on research findings.

## Pipeline Steps

| Step | Agent | Output |
|------|-------|--------|
| 1 | **Concierge** | Validated intake, research brief |
| 2 | **CompanyIntelligence** | Company profile + economic situation |
| 3 | **StrategicSignals** | Industry analysis + overcapacity signals |
| 4 | **MarketNetwork** | 4-tier buyer network (see below) |
| 5 | **EvidenceQA** | Quality review, gap identification |
| 6 | **Synthesis** | Final briefing with pro/contra per option |

## Buyer Pyramid (Step 4)

```
┌─────────────────────────────────────┐
│  PEER COMPETITORS                   │
│  Same/similar products              │
│  → Potential buyers of parts        │
├─────────────────────────────────────┤
│  DOWNSTREAM BUYERS                  │
│  Buy products from Intake + Peers   │
│  → Including unknown customers      │
│  → Including spare-part users       │
├─────────────────────────────────────┤
│  SERVICE PROVIDERS                  │
│  Maintain/repair equipment          │
│  → Need spare parts                 │
├─────────────────────────────────────┤
│  CROSS-INDUSTRY BUYERS              │
│  Other industries                   │
│  → Alternative use cases            │
└─────────────────────────────────────┘
```

## Architecture

- **AutoGen GroupChat** with FSM-controlled speaker transitions
- **7 agents** (Admin + 6 pipeline agents)
- **Pydantic models** for structured outputs
- **Artifact export** to `artifacts/runs/<run_id>/`

### FSM Flow

```
Admin → Concierge → CompanyIntelligence → StrategicSignals
  ↑                                            ↓
  └── Synthesis ← EvidenceQA ←──────── MarketNetwork
                       ↓
               (can loop back to CompanyIntelligence)
```

## Project Structure

```
src/
  config/          # Runtime configuration
  models/          # Pydantic schemas for all outputs
  agents/          # Agent definitions + group chat setup
  exporters/       # JSON artifact export
  pipeline.py      # Main entry point
artifacts/
  runs/            # Output per run
```

## Usage

```bash
pip install -r requirements.txt
python -m src.pipeline
```

Set `OPENAI_API_KEY` in `.env`.

Optional: `LLM_MODEL=gpt-4` (default) or `LLM_MODEL=gpt-4o`.
