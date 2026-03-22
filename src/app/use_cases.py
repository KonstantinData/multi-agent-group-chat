"""Shared use-case definitions for Liquisto preparation runs."""
from __future__ import annotations

from typing import Any


LIQUISTO_STANDARD_SCOPE = """
Prepare a Liquisto pre-meeting briefing for a new target company.

The briefing must help a Liquisto colleague prepare for a customer meeting where
Liquisto wants to understand the target company, its market situation, and the
most plausible value-creation paths for a future commercial engagement.

Always investigate these information blocks:
1. Company fundamentals: identity, products, offering, footprint, visible leadership, and business model.
2. Economic and commercial situation: signs of pressure, growth, contraction, inventory stress, demand weakness, shortage/excess dynamics, liquidity pressure, or strategic change.
3. Market situation: demand trend, supply pressure, overcapacity, growth/stagnation/decline, and why.
4. Peer companies: direct and close competitors producing the same or similar goods.
5. Product and asset scope: identify which goods, components, materials, spare parts, or inventory positions are visible in the target company. Distinguish between products the company appears to make itself, products it mainly distributes or resells, and materials, spare parts, or stock it holds. Include internal assets only when they appear relevant for inventory, redeployment, repurposing, or operational analysis. Highlight which items are most likely to matter for later buyer, resale, redeployment, repurposing, aftermarket, or inventory-management analysis, and explain why.
6. Monetization and redeployment landscape: identify plausible resale, redeployment, reuse, or secondary-market paths for the goods and assets identified above. This includes specific peer buyers, downstream customers, aftermarket or service organizations, distributors, brokers, marketplaces, and cross-industry users where there is a credible fit. State what each buyer path may absorb and why it is relevant.
7. Repurposing and circularity landscape: identify plausible repurposing paths for unused materials, components, or assets, including adjacent use cases, circular-economy pathways, innovation partners, or communities when relevant.
8. Analytics and operational improvement landscape: identify signals of reporting gaps, planning complexity, inventory visibility problems, decision bottlenecks, or resource-efficiency opportunities where analytics or decision support could create value.
9. Liquisto opportunity assessment: only after completing the research, assess which Liquisto path appears most plausible based on the evidence and why. The possible outcomes are:
   - excess inventory monetization and inventory optimization
   - repurposing and circular-economy use cases for unused materials
   - analytics, reporting, and decision support for resource efficiency
   - or a combination of these paths when the evidence supports it
10. Negotiation relevance: signals that help Liquisto estimate pricing power, urgency, buyer demand, repurposing leverage, analytics potential, and the strongest next commercial angle for the meeting.

The user only provides company name and web domain. The system must infer the
rest of the standard research scope automatically.
""".strip()


STANDARD_TASK_BACKLOG: list[dict[str, Any]] = [
    {
        "task_key": "company_fundamentals",
        "label": "Company fundamentals",
        "assignee": "CompanyDepartment",
        "target_section": "company_profile",
        "objective_template": "Build verified company fundamentals for {company_name}, including identity, offering, footprint, and business model.",
    },
    {
        "task_key": "economic_commercial_situation",
        "label": "Economic and commercial situation",
        "assignee": "CompanyDepartment",
        "target_section": "company_profile",
        "objective_template": "Assess public signals of economic and commercial pressure for {company_name}, including growth, contraction, inventory stress, shortage or excess dynamics, and strategic change.",
    },
    {
        "task_key": "market_situation",
        "label": "Market situation",
        "assignee": "MarketDepartment",
        "target_section": "industry_analysis",
        "objective_template": "Assess the market situation for {company_name}: demand trend, supply pressure, overcapacity, growth or decline, and why.",
    },
    {
        "task_key": "peer_companies",
        "label": "Peer companies",
        "assignee": "BuyerDepartment",
        "target_section": "market_network",
        "objective_template": "Identify direct and close peer companies producing the same or similar goods as {company_name}.",
    },
    {
        "task_key": "product_asset_scope",
        "label": "Product and asset scope",
        "assignee": "CompanyDepartment",
        "target_section": "company_profile",
        "objective_template": "Identify which goods, components, materials, spare parts, or inventory positions are visible in {company_name}. Distinguish between products the company appears to make itself, products it mainly distributes or resells, and materials, spare parts, or stock it holds. Include internal assets only when they appear relevant for inventory, redeployment, repurposing, or operational analysis, and highlight which items matter most for later buyer, resale, redeployment, repurposing, aftermarket, or inventory-management analysis.",
    },
    {
        "task_key": "monetization_redeployment",
        "label": "Monetization and redeployment landscape",
        "assignee": "BuyerDepartment",
        "target_section": "market_network",
        "objective_template": "Identify plausible resale, redeployment, reuse, and secondary-market paths for the goods and assets identified for {company_name}, including likely buyers and why each route is relevant.",
    },
    {
        "task_key": "repurposing_circularity",
        "label": "Repurposing and circularity landscape",
        "assignee": "MarketDepartment",
        "target_section": "industry_analysis",
        "objective_template": "Identify plausible repurposing and circularity paths for unused materials, components, or adjacent assets from {company_name}.",
    },
    {
        "task_key": "analytics_operational_improvement",
        "label": "Analytics and operational improvement landscape",
        "assignee": "MarketDepartment",
        "target_section": "industry_analysis",
        "objective_template": "Identify planning, reporting, inventory-visibility, or decision-support signals where analytics could create value for {company_name}.",
    },
    {
        "task_key": "contact_discovery",
        "label": "Contact discovery at prioritized buyer firms",
        "assignee": "ContactDepartment",
        "target_section": "contact_intelligence",
        "objective_template": "Identify publicly visible decision-makers and relevant contacts at buyer firms identified for {company_name}. Focus on procurement, asset management, operations, and supply chain functions.",
    },
    {
        "task_key": "contact_qualification",
        "label": "Contact qualification and outreach angles",
        "assignee": "ContactDepartment",
        "target_section": "contact_intelligence",
        "objective_template": "Qualify identified contacts for {company_name} buyer firms by seniority, function, and Liquisto relevance. Suggest a concrete outreach angle per contact based on the buyer context.",
    },
    {
        "task_key": "liquisto_opportunity_assessment",
        "label": "Liquisto opportunity assessment",
        "assignee": "SynthesisDepartment",
        "target_section": "synthesis",
        "objective_template": "After the research is complete, assess which Liquisto path is most plausible for {company_name} based on the evidence and explain why.",
    },
    {
        "task_key": "negotiation_relevance",
        "label": "Negotiation relevance",
        "assignee": "SynthesisDepartment",
        "target_section": "synthesis",
        "objective_template": "Summarize signals that help Liquisto estimate urgency, pricing power, buyer demand, repurposing leverage, analytics potential, and the strongest next meeting angle for {company_name}.",
    },
]


def build_standard_scope() -> str:
    """Return the canonical Liquisto research mandate."""
    return LIQUISTO_STANDARD_SCOPE


def build_standard_backlog() -> list[dict[str, Any]]:
    """Return the canonical supervisor task backlog."""
    return [dict(item) for item in STANDARD_TASK_BACKLOG]
