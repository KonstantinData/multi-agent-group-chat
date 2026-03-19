"""Liquisto Market Intelligence Pipeline – AutoGen Group Chat."""
from __future__ import annotations

import uuid
from src.config import get_llm_config
from src.agents import create_agents, create_group_chat
from src.exporters import export_run


def main() -> None:
    company_name = input("Company Name: ").strip()
    web_domain = input("Web Domain: ").strip()

    if not company_name or not web_domain:
        print("Error: Company name and web domain are required.")
        return

    task = (
        f"Research the company '{company_name}' (domain: {web_domain}) "
        f"for a Liquisto sales meeting preparation.\n\n"
        f"Run the full pipeline:\n"
        f"1. Concierge: Validate intake and build research brief\n"
        f"2. CompanyIntelligence: Build comprehensive company profile\n"
        f"3. StrategicSignals: Analyze industry trends and overcapacity signals\n"
        f"4. MarketNetwork: Identify buyers across 4 tiers "
        f"(Peer Competitors → Downstream Buyers → Service Providers → Cross-Industry)\n"
        f"5. EvidenceQA: Review evidence quality and flag gaps\n"
        f"6. Synthesis: Compile final briefing with pro/contra arguments "
        f"for Kaufen/Kommission/Ablehnen and Liquisto service area relevance\n\n"
        f"Each agent outputs structured JSON matching the defined schemas."
    )

    llm_config = get_llm_config()
    agents = create_agents(llm_config)
    groupchat, manager = create_group_chat(agents, llm_config)

    result = agents["admin"].initiate_chat(manager, message=task)

    run_id = uuid.uuid4().hex[:12]
    run_dir = export_run(run_id, result)
    print(f"\nResults exported to: {run_dir}")


if __name__ == "__main__":
    main()
