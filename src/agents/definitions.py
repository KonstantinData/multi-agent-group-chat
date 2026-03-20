"""Agent definitions for the Liquisto Market Intelligence Pipeline."""
from __future__ import annotations

import json
import os

import autogen
from autogen.agentchat.group import (
    AgentNameTarget,
    ContextVariables,
    ExpressionContextCondition,
    FunctionTarget,
    FunctionTargetResult,
    OnContextCondition,
    TerminateTarget,
)
from autogen.agentchat.group.context_expression import ContextExpression
from autogen.agentchat.group.patterns import DefaultPattern

from src.config import get_llm_config
from src.models.schemas import (
    CompanyProfile,
    ConciergeOutput,
    IndustryAnalysis,
    MarketNetwork,
    QualityReview,
    ReviewFeedback,
    SynthesisReport,
)
from src.tools import register_research_tools

MAX_STAGE_ATTEMPTS = int(os.environ.get("PIPELINE_MAX_STAGE_ATTEMPTS", "3"))
WORKFLOW_COMPLETE_KEY = "workflow_complete"
WORKFLOW_STAGE_KEYS = [
    "concierge",
    "company_intelligence",
    "strategic_signals",
    "market_network",
    "evidence_qa",
    "synthesis",
]

SOURCE_FRESHNESS_POLICY = (
    "Prefer sources from the last 24 months for company facts and the last 18 months for "
    "industry signals. If only older evidence exists for unstable facts like revenue, "
    "profitability, market size, growth, or demand outlook, return 'n/v' instead of stale estimates. "
    "Every important numeric or economic claim must be traceable to at least one cited source."
)

TOOL_BUDGET_POLICY = (
    "Use only a small number of high-value tool calls. Prefer 1-3 focused searches or fetches, then finalize. "
    "If evidence remains incomplete after a few tool calls, stop researching and return conservative fields such as "
    "'n/v' or empty lists instead of continuing to search indefinitely."
)

BUYER_EVIDENCE_POLICY = (
    "Do not invent buyers. Each buyer must be linked to a concrete matching product or use case. "
    "Use 'candidate' for plausible but weakly evidenced buyers, 'qualified' only when there is "
    "explicit evidence of product fit, customer fit, or documented sector overlap, and 'verified' "
    "only for direct documented relationships or procurement/service evidence. If a tier has no "
    "credible buyers, return an empty companies list for that tier."
)


def _agent_llm_config(response_format: type) -> object:
    return get_llm_config(response_format=response_format)


def _critic_system_message(subject: str, expectations: str) -> str:
    return (
        f"You are the critic for {subject}. "
        "Review the latest producer output against the expectations below. "
        "Approve only when the output is schema-complete, evidence-conscious, conservative about uncertainty, "
        "and internally consistent. "
        "If you reject it, provide concrete revision instructions the same producer can apply immediately. "
        "When evidence is missing or weak, instruct the producer to downgrade, remove, empty, or set fields to 'n/v' "
        "instead of asking for stronger unsupported claims. Never ask the producer to upgrade evidence tiers, invent "
        "specific citations, or fabricate verification that is not already grounded in the available context. "
        "Return only structured output matching the configured schema.\n\n"
        f"Expectations:\n{expectations}"
    )


def create_agents(_manager_llm_config: object | None = None) -> dict[str, autogen.ConversableAgent]:
    """Create and return all pipeline agents."""

    admin = autogen.ConversableAgent(
        name="Admin",
        system_message=(
            "You are the Admin of a Liquisto market intelligence pipeline. "
            "Acknowledge the task, start the workflow, and close the orchestration once the final review has passed."
        ),
        description="Admin. Starts the AG2 workflow and closes it after the final approved review.",
        code_execution_config=False,
        llm_config=False,
        human_input_mode="NEVER",
        default_auto_reply="Admin acknowledged. Proceed with the configured workflow.",
    )

    concierge = autogen.ConversableAgent(
        name="Concierge",
        system_message=(
            "You are the Concierge agent. Your job is to validate the intake input "
            "(company name + web domain) and build a structured research brief. "
            "Verify the domain is reachable, confirm the company name matches, "
            "and produce a clear research brief with: company_name, web_domain, "
            "language (de/en), and any initial observations from the website. "
            "Keep observations factual and concise. "
            "Do not infer products, services, industry, or company situation at this stage. "
            "Only include observations that can be stated conservatively from the intake or obvious site-level cues. "
            "If content details are unclear, keep observations minimal or empty. "
            "Use the available research tools, especially check_domain and fetch_page, before concluding reachability or language. "
            "For this stage, do not search broadly; one domain check and at most one page fetch are usually enough. "
            f"{TOOL_BUDGET_POLICY} "
            "Return only structured output matching the configured schema."
        ),
        description="Concierge. Validates intake input and builds the research brief.",
        llm_config=_agent_llm_config(ConciergeOutput),
    )

    company_intelligence = autogen.ConversableAgent(
        name="CompanyIntelligence",
        system_message=(
            "You are the Company Intelligence agent. Based on the research brief, "
            "build a comprehensive company profile including:\n"
            "- Legal name, legal form, founding year, headquarters\n"
            "- Industry, employees, revenue\n"
            "- Products and services (detailed – this is critical for downstream buyer research)\n"
            "- Key people (management, board)\n"
            "- Economic situation: revenue trend, profitability, recent events, "
            "inventory signals, financial pressure\n\n"
            "Use the company website, Impressum, annual reports, press releases, "
            "and public registers as sources. Mark unverifiable fields as 'n/v'. "
            "Use the available research tools to search and fetch primary sources before filling company facts. "
            "Start with company_source_pack(company_name, domain), then fetch only the 1-3 most relevant official or registry-style pages. "
            "Prioritize official site pages, sustainability/annual reports, and registry/profile pages. "
            "Do not keep searching for missing revenue or employee data after the first focused pass; return 'n/v' if still unsupported. "
            f"{TOOL_BUDGET_POLICY} "
            f"{SOURCE_FRESHNESS_POLICY} "
            "Return only structured output matching the configured schema."
        ),
        description="CompanyIntelligence. Researches and builds the full company profile.",
        llm_config=_agent_llm_config(CompanyProfile),
    )

    strategic_signals = autogen.ConversableAgent(
        name="StrategicSignals",
        system_message=(
            "You are the Strategic Signals agent. Based on the company profile, "
            "analyze the industry landscape:\n"
            "- Industry name, market size, growth rate, trend direction\n"
            "- Key trends affecting the sector\n"
            "- Overcapacity signals and excess stock indicators\n"
            "- Demand outlook\n\n"
            "Focus on signals relevant to Liquisto's business: excess inventory, "
            "overproduction, market shifts that create surplus goods. "
            "Use the available research tools to search for recent industry reports and fetch source pages before stating trends. "
            "Start with industry_source_pack(company_name, industry_hint, product_keywords), then fetch at most 1-2 promising industry pages. "
            "Prefer industry-specific sources over generic macro searches. If targeted searches stay weak, keep market_size, growth_rate, and demand_outlook at 'n/v'. "
            f"{TOOL_BUDGET_POLICY} "
            f"{SOURCE_FRESHNESS_POLICY} "
            "Return only structured output matching the configured schema."
        ),
        description="StrategicSignals. Analyzes industry trends, overcapacity, and market signals.",
        llm_config=_agent_llm_config(IndustryAnalysis),
    )

    market_network = autogen.ConversableAgent(
        name="MarketNetwork",
        system_message=(
            "You are the Market Network agent. Based on the company profile and "
            "industry analysis, identify potential buyers across 4 tiers:\n\n"
            "1. PEER COMPETITORS: Companies producing same/similar products as the "
            "intake company. These are competitors who might buy individual parts "
            "for their own production.\n\n"
            "2. DOWNSTREAM BUYERS: Companies that buy finished products from the "
            "intake company AND from the identified peers. Include companies not yet "
            "known as customers. Also include companies that could use individual "
            "parts as spare parts.\n\n"
            "3. SERVICE PROVIDERS: Companies that maintain, repair, or service the "
            "equipment/products made by the intake company and peers. They need "
            "spare parts.\n\n"
            "4. CROSS-INDUSTRY BUYERS: Companies from completely different industries "
            "that could use the products or parts for alternative purposes.\n\n"
            "For each buyer provide: name, website, location, relevance explanation, "
            "matching products, and evidence tier. "
            "Use the available research tools to find concrete buyer evidence before listing companies. "
            "Start with buyer_source_pack(company_name, product_keywords, domain), then fetch only the strongest candidate pages. "
            "Prefer competitors, customers, case studies, distributors, service pages, and aftermarket pages over generic buyer searches. "
            "If no concrete evidence appears quickly, keep tiers empty instead of filling them with speculative names. "
            f"{TOOL_BUDGET_POLICY} "
            f"{BUYER_EVIDENCE_POLICY} "
            "Prefer fresh evidence. If a tier is supported only by stale or generic evidence, "
            "state that in the assessment and keep evidence_tier conservative. "
            "Return only structured output matching the configured schema."
        ),
        description=(
            "MarketNetwork. Identifies buyers across 4 tiers: "
            "Peer Competitors, Downstream Buyers, Service Providers, Cross-Industry Buyers."
        ),
        llm_config=_agent_llm_config(MarketNetwork),
    )

    evidence_qa = autogen.ConversableAgent(
        name="EvidenceQA",
        system_message=(
            "You are the Evidence QA agent. Review ALL outputs from previous agents "
            "and assess evidence quality:\n"
            "- Which claims are well-sourced vs. unverified?\n"
            "- Are there critical gaps in the company profile?\n"
            "- Are buyer identifications backed by real evidence?\n"
            "- Are there logical inconsistencies?\n"
            "- Are sources too old for the claims being made?\n\n"
            "Actively reject stale or weak evidence. "
            "If economic or market data is older than about 24 months, call it out explicitly. "
            "If buyer tiers are dominated by candidate-level evidence or generic sector overlap, "
            "call that out explicitly. "
            "Produce a quality review listing: validated agents, evidence health, "
            "open gaps, and recommendations for improvement. "
            "If gaps are critical, clearly state which agent should rework what. "
            "Return only structured output matching the configured schema."
        ),
        description="EvidenceQA. Reviews evidence quality and identifies gaps across all agent outputs.",
        llm_config=_agent_llm_config(QualityReview),
    )

    synthesis = autogen.ConversableAgent(
        name="Synthesis",
        system_message=(
            "You are the Synthesis agent. Compile all research into a final briefing "
            "for the Liquisto sales team. Your report must include:\n\n"
            "1. EXECUTIVE SUMMARY: Who is this company, what do they make, what's "
            "their situation?\n\n"
            "2. LIQUISTO SERVICE RELEVANCE: For each of the 3 Liquisto areas, assess "
            "relevance (hoch/mittel/niedrig/unklar) with reasoning:\n"
            "   - Excess Inventory (one-stop platform for surplus optimization)\n"
            "   - Repurposing (collaborative ideation for unused materials)\n"
            "   - Analytics (value chain analytics as a service)\n\n"
            "3. CASE ASSESSMENT: For each option (Kaufen/Kommission/Ablehnen), "
            "provide ARGUMENTS pro and contra with the evidence they are based on. "
            "Do NOT make a recommendation. Present the arguments transparently so "
            "the Liquisto team can decide in the meeting.\n\n"
            "4. BUYER MARKET SUMMARY: How strong is the buyer market across all 4 tiers?\n\n"
            "5. KEY RISKS and NEXT STEPS for the meeting.\n\n"
            "Do not present stale or weak evidence as firm conclusions. "
            "If QA found outdated sources or candidate-heavy buyer tiers, reflect that uncertainty "
            "directly in the executive summary, buyer market summary, key risks, and next steps. "
            "Return only structured output matching the configured schema."
        ),
        description=(
            "Synthesis. Compiles final briefing with pro/contra assessments "
            "for each Liquisto option."
        ),
        llm_config=_agent_llm_config(SynthesisReport),
    )

    concierge_critic = autogen.ConversableAgent(
        name="ConciergeCritic",
        system_message=_critic_system_message(
            "Concierge",
            "- company_name and web_domain must match the intake\n"
            "- language should reflect the visible site language\n"
            "- observations must be factual, concise, non-speculative, and limited to intake/domain-level cues\n"
            "- do not require product, service, or industry claims in this stage",
        ),
        description="Critic for Concierge output.",
        llm_config=_agent_llm_config(ReviewFeedback),
    )

    company_intelligence_critic = autogen.ConversableAgent(
        name="CompanyIntelligenceCritic",
        system_message=_critic_system_message(
            "CompanyIntelligence",
            "- core company facts should be grounded in cited sources\n"
            "- volatile metrics without fresh evidence must be n/v\n"
            "- products, people, and economic statements must not be invented\n"
            "- sources should be recent enough for the claims being made",
        ),
        description="Critic for CompanyIntelligence output.",
        llm_config=_agent_llm_config(ReviewFeedback),
    )

    strategic_signals_critic = autogen.ConversableAgent(
        name="StrategicSignalsCritic",
        system_message=_critic_system_message(
            "StrategicSignals",
            "- market size, growth, and demand outlook need fresh evidence or n/v\n"
            "- trends and overcapacity signals must be relevant to the target industry\n"
            "- avoid generic macro statements unless they are tied to the sector",
        ),
        description="Critic for StrategicSignals output.",
        llm_config=_agent_llm_config(ReviewFeedback),
    )

    market_network_critic = autogen.ConversableAgent(
        name="MarketNetworkCritic",
        system_message=_critic_system_message(
            "MarketNetwork",
            "- buyers must have concrete product fit or use-case fit\n"
            "- evidence_tier must be conservative and justified\n"
            "- empty tiers are better than speculative buyer lists\n"
            "- tier assessments should reflect evidence strength honestly",
        ),
        description="Critic for MarketNetwork output.",
        llm_config=_agent_llm_config(ReviewFeedback),
    )

    evidence_qa_critic = autogen.ConversableAgent(
        name="EvidenceQACritic",
        system_message=_critic_system_message(
            "EvidenceQA",
            "- open_gaps should capture the most important missing evidence\n"
            "- recommendations should be actionable and target the right producer\n"
            "- evidence_health should reflect the real quality of the run",
        ),
        description="Critic for EvidenceQA output.",
        llm_config=_agent_llm_config(ReviewFeedback),
    )

    synthesis_critic = autogen.ConversableAgent(
        name="SynthesisCritic",
        system_message=_critic_system_message(
            "Synthesis",
            "- no new facts beyond prior validated outputs\n"
            "- uncertainty and QA findings must be reflected in the summary, risks, and next steps\n"
            "- buyer-market strength must not exceed the actual evidence quality\n"
            "- option assessments must stay balanced and evidence-based",
        ),
        description="Critic for Synthesis output.",
        llm_config=_agent_llm_config(ReviewFeedback),
    )

    register_research_tools(concierge, ["check_domain", "fetch_page"])
    register_research_tools(company_intelligence, ["company_source_pack", "fetch_page", "web_search"])
    register_research_tools(strategic_signals, ["industry_source_pack", "fetch_page", "web_search"])
    register_research_tools(market_network, ["buyer_source_pack", "fetch_page", "web_search"])

    return {
        "admin": admin,
        "concierge": concierge,
        "concierge_critic": concierge_critic,
        "company_intelligence": company_intelligence,
        "company_intelligence_critic": company_intelligence_critic,
        "strategic_signals": strategic_signals,
        "strategic_signals_critic": strategic_signals_critic,
        "market_network": market_network,
        "market_network_critic": market_network_critic,
        "evidence_qa": evidence_qa,
        "evidence_qa_critic": evidence_qa_critic,
        "synthesis": synthesis,
        "synthesis_critic": synthesis_critic,
    }


def create_group_pattern(
    agents: dict[str, autogen.ConversableAgent],
    llm_config: object | None = None,
) -> DefaultPattern:
    """Create the AG2-native producer/critic workflow as a handoff-driven pattern."""
    _configure_workflow_handoffs(agents)
    max_round = 1 + (len(WORKFLOW_STAGE_KEYS) * MAX_STAGE_ATTEMPTS * 2) + 2
    return DefaultPattern(
        initial_agent=agents["admin"],
        agents=list(agents.values()),
        context_variables=ContextVariables.from_dict({WORKFLOW_COMPLETE_KEY: False}),
        group_manager_args={
            "llm_config": False,
            "human_input_mode": "NEVER",
            "silent": True,
            "max_consecutive_auto_reply": max_round,
            "system_message": (
                "You are the AG2 workflow manager. Enforce agent handoffs, tool execution, and termination."
            ),
        },
    )


def _configure_workflow_handoffs(agents: dict[str, autogen.ConversableAgent]) -> None:
    for agent in agents.values():
        agent.handoffs.clear()

    agents["admin"].handoffs.add_after_works(
        [
            OnContextCondition(
                target=TerminateTarget(),
                condition=ExpressionContextCondition(ContextExpression(f"${{{WORKFLOW_COMPLETE_KEY}}} == True")),
            ),
            OnContextCondition(target=AgentNameTarget(agents["concierge"].name), condition=None),
        ]
    )

    ordered_pairs = [
        ("concierge", "concierge_critic"),
        ("company_intelligence", "company_intelligence_critic"),
        ("strategic_signals", "strategic_signals_critic"),
        ("market_network", "market_network_critic"),
        ("evidence_qa", "evidence_qa_critic"),
        ("synthesis", "synthesis_critic"),
    ]

    for index, (producer_key, critic_key) in enumerate(ordered_pairs):
        producer = agents[producer_key]
        critic = agents[critic_key]
        next_target_name = (
            agents["admin"].name if index == len(ordered_pairs) - 1 else agents[ordered_pairs[index + 1][0]].name
        )
        is_final_stage = index == len(ordered_pairs) - 1

        producer.handoffs.set_after_work(AgentNameTarget(critic.name))
        critic.handoffs.set_after_work(
            FunctionTarget(
                _route_stage_review,
                extra_args={
                    "producer_name": producer.name,
                    "next_target_name": next_target_name,
                    "attempts_key": f"{producer_key}_attempts",
                    "complete_workflow": is_final_stage,
                },
            )
        )


def _parse_review_feedback_message(content: str) -> dict[str, bool]:
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return {"approved": False}

    try:
        review = ReviewFeedback.model_validate(payload)
    except Exception:
        return {"approved": False}

    return {"approved": bool(review.approved)}


def _route_stage_review(
    output: str,
    context_variables: ContextVariables,
    producer_name: str,
    next_target_name: str,
    attempts_key: str,
    complete_workflow: bool = False,
) -> FunctionTargetResult:
    review = _parse_review_feedback_message(output)
    attempts = int(context_variables.get(attempts_key, 0) or 0) + 1

    updated_context = ContextVariables.from_dict(
        {
            attempts_key: attempts,
            f"{producer_name}_approved": bool(review["approved"]),
            WORKFLOW_COMPLETE_KEY: bool(complete_workflow and review["approved"]),
        }
    )

    if review["approved"] or attempts >= MAX_STAGE_ATTEMPTS:
        if complete_workflow:
            updated_context.set(WORKFLOW_COMPLETE_KEY, True)
        return FunctionTargetResult(
            context_variables=updated_context,
            target=AgentNameTarget(next_target_name),
        )

    feedback = _build_revision_message(output)
    return FunctionTargetResult(
        messages=feedback,
        context_variables=updated_context,
        target=AgentNameTarget(producer_name),
    )


def _build_revision_message(content: str) -> str:
    try:
        review = ReviewFeedback.model_validate_json(content)
    except Exception:
        return (
            "Revise your previous structured output. The critic did not approve it. "
            "Be more conservative, fix missing required fields, and do not invent unsupported evidence."
        )

    parts: list[str] = ["Revise your previous structured output using the critic feedback below."]
    if review.issues:
        parts.append("Issues: " + " | ".join(review.issues))
    if review.revision_instructions:
        parts.append("Instructions: " + " | ".join(review.revision_instructions))
    parts.append("Keep the same schema and stay conservative about uncertainty.")
    return "\n".join(parts)
