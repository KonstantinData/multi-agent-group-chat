"""Agent definitions for the Liquisto Market Intelligence Pipeline."""
from __future__ import annotations

import autogen


def create_agents(llm_config: dict) -> dict[str, autogen.ConversableAgent]:
    """Create and return all pipeline agents."""

    admin = autogen.ConversableAgent(
        name="Admin",
        system_message=(
            "You are the Admin of a Liquisto market intelligence pipeline. "
            "You initiate the research with a company name and web domain. "
            "When the Synthesis agent delivers the final report, reply with TERMINATE."
        ),
        description="Admin. Initiates the research task. Replies TERMINATE when synthesis is done.",
        code_execution_config=False,
        llm_config=llm_config,
        human_input_mode="NEVER",
        is_termination_msg=lambda msg: "TERMINATE" in (msg.get("content") or ""),
    )

    concierge = autogen.ConversableAgent(
        name="Concierge",
        system_message=(
            "You are the Concierge agent. Your job is to validate the intake input "
            "(company name + web domain) and build a structured research brief. "
            "Verify the domain is reachable, confirm the company name matches, "
            "and produce a clear research brief with: company_name, web_domain, "
            "language (de/en), and any initial observations from the website. "
            "Output your result as a structured research brief in JSON format."
        ),
        description="Concierge. Validates intake input and builds the research brief.",
        llm_config=llm_config,
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
            "Output as JSON matching the CompanyProfile schema."
        ),
        description="CompanyIntelligence. Researches and builds the full company profile.",
        llm_config=llm_config,
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
            "Output as JSON matching the IndustryAnalysis schema."
        ),
        description="StrategicSignals. Analyzes industry trends, overcapacity, and market signals.",
        llm_config=llm_config,
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
            "Output as JSON matching the MarketNetwork schema."
        ),
        description=(
            "MarketNetwork. Identifies buyers across 4 tiers: "
            "Peer Competitors, Downstream Buyers, Service Providers, Cross-Industry Buyers."
        ),
        llm_config=llm_config,
    )

    evidence_qa = autogen.ConversableAgent(
        name="EvidenceQA",
        system_message=(
            "You are the Evidence QA agent. Review ALL outputs from previous agents "
            "and assess evidence quality:\n"
            "- Which claims are well-sourced vs. unverified?\n"
            "- Are there critical gaps in the company profile?\n"
            "- Are buyer identifications backed by real evidence?\n"
            "- Are there logical inconsistencies?\n\n"
            "Produce a quality review listing: validated agents, evidence health, "
            "open gaps, and recommendations for improvement. "
            "If gaps are critical, clearly state which agent should rework what. "
            "Output as JSON matching the QualityReview schema."
        ),
        description="EvidenceQA. Reviews evidence quality and identifies gaps across all agent outputs.",
        llm_config=llm_config,
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
            "Output as JSON matching the SynthesisReport schema."
        ),
        description=(
            "Synthesis. Compiles final briefing with pro/contra assessments "
            "for each Liquisto option."
        ),
        llm_config=llm_config,
    )

    return {
        "admin": admin,
        "concierge": concierge,
        "company_intelligence": company_intelligence,
        "strategic_signals": strategic_signals,
        "market_network": market_network,
        "evidence_qa": evidence_qa,
        "synthesis": synthesis,
    }


def create_group_chat(agents: dict[str, autogen.ConversableAgent], llm_config: dict) -> tuple[autogen.GroupChat, autogen.GroupChatManager]:
    """Create the group chat with FSM transitions."""

    a = agents  # shorthand

    # FSM: enforces the logical pipeline flow
    allowed_transitions = {
        a["admin"]:                 [a["concierge"]],
        a["concierge"]:             [a["company_intelligence"]],
        a["company_intelligence"]:  [a["strategic_signals"]],
        a["strategic_signals"]:     [a["market_network"]],
        a["market_network"]:        [a["evidence_qa"]],
        a["evidence_qa"]:           [a["synthesis"], a["company_intelligence"]],  # can loop back
        a["synthesis"]:             [a["admin"]],
    }

    groupchat = autogen.GroupChat(
        agents=list(agents.values()),
        messages=[],
        max_round=25,
        allowed_or_disallowed_speaker_transitions=allowed_transitions,
        speaker_transitions_type="allowed",
    )

    manager = autogen.GroupChatManager(
        groupchat=groupchat,
        llm_config=llm_config,
    )

    return groupchat, manager
