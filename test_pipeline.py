"""Targeted tests for the AG2-native Liquisto pipeline."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import autogen

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.agents.definitions import create_group_pattern
from src.exporters.pdf_report import generate_pdf
from src.pipeline_runner import (
    _collect_usage_summary,
    _extract_pipeline_data,
    _prepare_group_chat,
    _resolve_group_chat_entrypoint,
    _try_parse_json,
)
from src.tools.research import _build_buyer_queries, _build_company_queries, _build_industry_queries


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _concierge_reply() -> str:
    return json.dumps(
        {
            "company_name": "imsgear SE",
            "web_domain": "imsgear.com",
            "language": "de",
            "observations": ["Website reachable."],
        }
    )


def _company_reply(revenue: str = "n/v") -> str:
    return json.dumps(
        {
            "company_name": "IMS Gear SE & Co. KGaA",
            "legal_form": "SE & Co. KGaA",
            "founded": "1863",
            "headquarters": "Donaueschingen, Germany",
            "website": "https://www.imsgear.com",
            "industry": "Machinery/Mechanical Engineering",
            "employees": "2775",
            "revenue": revenue,
            "products_and_services": ["Gear components", "Transmission systems"],
            "key_people": [{"name": "Bernd Schilling", "role": "Managing Director"}],
            "description": "IMS Gear manufactures gears and transmission technology.",
            "economic_situation": {
                "revenue_trend": "n/v",
                "profitability": "n/v",
                "recent_events": [],
                "inventory_signals": [],
                "financial_pressure": "n/v",
                "assessment": "n/v",
            },
            "sources": [],
        }
    )


def _industry_reply() -> str:
    return json.dumps(
        {
            "industry_name": "Machinery/Mechanical Engineering",
            "market_size": "n/v",
            "trend_direction": "unsicher",
            "growth_rate": "n/v",
            "key_trends": [],
            "overcapacity_signals": [],
            "excess_stock_indicators": "n/v",
            "demand_outlook": "n/v",
            "assessment": "n/v",
            "sources": [],
        }
    )


def _market_reply() -> str:
    empty_tier = {"companies": [], "assessment": "n/v", "sources": []}
    return json.dumps(
        {
            "target_company": "IMS Gear SE & Co. KGaA",
            "peer_competitors": empty_tier,
            "downstream_buyers": empty_tier,
            "service_providers": empty_tier,
            "cross_industry_buyers": empty_tier,
        }
    )


def _qa_reply() -> str:
    return json.dumps(
        {
            "validated_agents": ["Concierge", "CompanyIntelligence"],
            "evidence_health": "mittel",
            "open_gaps": ["No fresh revenue evidence."],
            "recommendations": ["Keep unsupported values at n/v."],
        }
    )


def _synthesis_reply() -> str:
    return json.dumps(
        {
            "target_company": "IMS Gear SE & Co. KGaA",
            "executive_summary": "IMS Gear is a mechanical engineering company with limited current financial evidence.",
            "liquisto_service_relevance": [
                {"service_area": "excess_inventory", "relevance": "unklar", "reasoning": "Insufficient proof."}
            ],
            "case_assessments": [
                {
                    "option": "kaufen",
                    "arguments": [
                        {
                            "argument": "Potential aftermarket relevance exists.",
                            "direction": "pro",
                            "based_on": "MarketNetwork",
                        }
                    ],
                    "summary": "Only a tentative case can be made.",
                }
            ],
            "buyer_market_summary": "Buyer evidence is weak.",
            "total_peer_competitors": 0,
            "total_downstream_buyers": 0,
            "total_service_providers": 0,
            "total_cross_industry_buyers": 0,
            "key_risks": ["Evidence is weak."],
            "next_steps": ["Research fresh primary sources."],
            "sources": [],
        }
    )


def _review(approved: bool, issue: str = "", instruction: str = "") -> str:
    payload = {
        "approved": approved,
        "issues": [issue] if issue else [],
        "revision_instructions": [instruction] if instruction else [],
    }
    return json.dumps(payload)


class SequenceAgent(autogen.ConversableAgent):
    def __init__(self, name: str, replies: list[str]):
        super().__init__(name=name, llm_config=False, human_input_mode="NEVER")
        self._replies = list(replies)
        self.calls = 0

    def generate_reply(self, messages=None, sender=None, exclude=()):  # type: ignore[override]
        self.calls += 1
        if not self._replies:
            raise RuntimeError(f"{self.name} has no reply configured for call {self.calls}")
        return self._replies.pop(0)


class FakeUsageAgent:
    def __init__(self, actual=None, total=None):
        self._actual = actual
        self._total = total

    def get_actual_usage(self):
        return self._actual

    def get_total_usage(self):
        return self._total


def _workflow_agents(*, company_replies=None, company_critic_replies=None) -> dict[str, autogen.ConversableAgent]:
    return {
        "admin": autogen.ConversableAgent(
            name="Admin",
            llm_config=False,
            human_input_mode="NEVER",
            default_auto_reply="Admin acknowledged. Proceed with the configured workflow.",
        ),
        "concierge": SequenceAgent("Concierge", [_concierge_reply()]),
        "concierge_critic": SequenceAgent("ConciergeCritic", [_review(True)]),
        "company_intelligence": SequenceAgent(
            "CompanyIntelligence",
            company_replies or [_company_reply()],
        ),
        "company_intelligence_critic": SequenceAgent(
            "CompanyIntelligenceCritic",
            company_critic_replies or [_review(True)],
        ),
        "strategic_signals": SequenceAgent("StrategicSignals", [_industry_reply()]),
        "strategic_signals_critic": SequenceAgent("StrategicSignalsCritic", [_review(True)]),
        "market_network": SequenceAgent("MarketNetwork", [_market_reply()]),
        "market_network_critic": SequenceAgent("MarketNetworkCritic", [_review(True)]),
        "evidence_qa": SequenceAgent("EvidenceQA", [_qa_reply()]),
        "evidence_qa_critic": SequenceAgent("EvidenceQACritic", [_review(True)]),
        "synthesis": SequenceAgent("Synthesis", [_synthesis_reply()]),
        "synthesis_critic": SequenceAgent("SynthesisCritic", [_review(True)]),
    }


def _run_pattern_chat(agents: dict[str, autogen.ConversableAgent], message: str):
    pattern = create_group_pattern(agents, llm_config=False)
    prepared_chat = _prepare_group_chat(pattern, max_rounds=20, messages=message)
    sender, initial_message, clear_history = _resolve_group_chat_entrypoint(
        prepared_chat,
        fallback_message=message,
    )
    return sender.initiate_chat(
        prepared_chat.manager,
        message=initial_message,
        clear_history=clear_history,
        summary_method=pattern.summary_method,
        silent=True,
    )


def test_groupchat_routes_full_workflow_in_order():
    agents = _workflow_agents()
    result = _run_pattern_chat(agents, "Research imsgear.com")

    workflow_names = {
        "Admin",
        "Concierge",
        "ConciergeCritic",
        "CompanyIntelligence",
        "CompanyIntelligenceCritic",
        "StrategicSignals",
        "StrategicSignalsCritic",
        "MarketNetwork",
        "MarketNetworkCritic",
        "EvidenceQA",
        "EvidenceQACritic",
        "Synthesis",
        "SynthesisCritic",
    }
    actual_order = [msg["name"] for msg in result.chat_history if msg.get("name") in workflow_names]
    expected_order = [
        "Admin",
        "Concierge",
        "ConciergeCritic",
        "CompanyIntelligence",
        "CompanyIntelligenceCritic",
        "StrategicSignals",
        "StrategicSignalsCritic",
        "MarketNetwork",
        "MarketNetworkCritic",
        "EvidenceQA",
        "EvidenceQACritic",
        "Synthesis",
        "SynthesisCritic",
        "Admin",
    ]
    assert actual_order == expected_order
    assert actual_order[-1] == "Admin"


def test_groupchat_retries_same_producer_after_critic_rejection():
    agents = _workflow_agents(
        company_replies=[_company_reply("EUR 124m"), _company_reply("n/v")],
        company_critic_replies=[
            _review(False, "Revenue unsupported.", "Set unsupported revenue to n/v."),
            _review(True),
        ],
    )
    result = _run_pattern_chat(agents, "Research imsgear.com")

    workflow_names = {
        "Admin",
        "Concierge",
        "ConciergeCritic",
        "CompanyIntelligence",
        "CompanyIntelligenceCritic",
        "StrategicSignals",
        "StrategicSignalsCritic",
        "MarketNetwork",
        "MarketNetworkCritic",
        "EvidenceQA",
        "EvidenceQACritic",
        "Synthesis",
        "SynthesisCritic",
    }
    order = [msg["name"] for msg in result.chat_history if msg.get("name") in workflow_names]
    company_indexes = [index for index, name in enumerate(order) if name == "CompanyIntelligence"]
    assert len(company_indexes) == 2
    assert order[company_indexes[0] + 1] == "CompanyIntelligenceCritic"
    assert order[company_indexes[1] - 1] == "CompanyIntelligenceCritic"
    assert "StrategicSignals" in order[company_indexes[1] + 1 :]


def test_research_query_builders_are_agent_specific():
    company_queries = _build_company_queries("IMS Gear SE & Co. KGaA", "imsgear.com")
    industry_queries = _build_industry_queries(
        "IMS Gear SE & Co. KGaA",
        "Transmission Technology",
        "Planetary gear systems, Low Noise Gear Systems",
    )
    buyer_queries = _build_buyer_queries(
        "IMS Gear SE & Co. KGaA",
        "Planetary gear systems, Low Noise Gear Systems",
        "imsgear.com",
    )

    assert any("site:imsgear.com" in query for query in company_queries)
    assert any("sustainability report" in query.lower() for query in company_queries)
    assert any("Transmission Technology" in query for query in industry_queries)
    assert any("market report 2023" in query.lower() for query in industry_queries)
    assert any("customers" in query.lower() for query in buyer_queries)
    assert any("competitors" in query.lower() for query in buyer_queries)
    assert any("site:imsgear.com" in query for query in buyer_queries)


def test_collect_usage_summary_aggregates_agents():
    usage = _collect_usage_summary(
        {
            "company": FakeUsageAgent(
                actual={
                    "total_cost": 0.01,
                    "gpt-4o-mini": {
                        "cost": 0.01,
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                        "total_tokens": 150,
                    },
                },
                total={
                    "total_cost": 0.02,
                    "gpt-4o-mini": {
                        "cost": 0.02,
                        "prompt_tokens": 120,
                        "completion_tokens": 80,
                        "total_tokens": 200,
                    },
                },
            ),
            "market": FakeUsageAgent(
                actual={
                    "total_cost": 0.005,
                    "gpt-4o-mini": {
                        "cost": 0.005,
                        "prompt_tokens": 40,
                        "completion_tokens": 10,
                        "total_tokens": 50,
                    },
                },
                total={
                    "total_cost": 0.007,
                    "gpt-4o-mini": {
                        "cost": 0.007,
                        "prompt_tokens": 60,
                        "completion_tokens": 10,
                        "total_tokens": 70,
                    },
                },
            ),
        }
    )

    assert usage["actual"]["total_cost"] == 0.015
    assert usage["actual"]["prompt_tokens"] == 140
    assert usage["actual"]["completion_tokens"] == 60
    assert usage["actual"]["total_tokens"] == 200
    assert usage["total"]["total_cost"] == 0.027
    assert usage["total"]["models"]["gpt-4o-mini"]["total_tokens"] == 270


def test_extract_pipeline_data_and_pdf_generation():
    messages = []

    def emit(agent: str, content: str, msg_type: str = "agent_message") -> None:
        messages.append(
            {
                "type": msg_type,
                "agent": agent,
                "content": content,
                "timestamp": _ts(),
            }
        )

    emit("Admin", "Research the company 'Lenze SE' (domain: lenze.com) for a Liquisto sales meeting preparation.")
    emit("Concierge", _concierge_reply())
    emit("CompanyIntelligence", _company_reply())
    emit("StrategicSignals", _industry_reply())
    emit("MarketNetwork", _market_reply())
    emit("EvidenceQA", _qa_reply())
    emit("Synthesis", _synthesis_reply())
    emit("Admin", "TERMINATE")

    pipeline_data = _extract_pipeline_data(messages)
    assert pipeline_data["company_profile"]
    assert pipeline_data["industry_analysis"]
    assert pipeline_data["market_network"]
    assert pipeline_data["quality_review"]
    assert pipeline_data["synthesis"]

    pdf_de = generate_pdf(pipeline_data, lang="de")
    pdf_en = generate_pdf(pipeline_data, lang="en")
    assert len(pdf_de) > 1000
    assert len(pdf_en) > 1000


def test_extract_pipeline_data_rejects_legacy_payload_shapes():
    legacy_company_payload = json.dumps(
        {
            "LegalInformation": {
                "LegalName": "IMS Gear SE & Co. KGaA",
                "LegalForm": "SE & Co. KGaA",
            },
            "IndustryAndMarket": {
                "Industry": "Machinery/Mechanical Engineering",
            },
        }
    )
    messages = [
        {
            "type": "agent_message",
            "agent": "CompanyIntelligence",
            "content": legacy_company_payload,
            "timestamp": _ts(),
        }
    ]

    pipeline_data = _extract_pipeline_data(messages)

    assert not pipeline_data["company_profile"]
    assert pipeline_data["validation_errors"]
    assert pipeline_data["validation_errors"][0]["agent"] == "CompanyIntelligence"
    assert pipeline_data["validation_errors"][0]["section"] == "company_profile"
    assert "company_name" in pipeline_data["validation_errors"][0]["details"]


def test_try_parse_json():
    test_cases = [
        ("direct json", '{"key": "value"}', True),
        ("markdown fence", '```json\n{"key": "value"}\n```', True),
        ("text + json", 'Here is the result:\n{"key": "value"}\nDone.', True),
        ("no json", "This is just text", False),
        ("empty", "", False),
    ]
    for _label, text, should_parse in test_cases:
        result = _try_parse_json(text)
        assert (result is not None) == should_parse


def main():
    print("=" * 60)
    print("AG2-NATIVE PIPELINE TEST")
    print("=" * 60)

    test_groupchat_routes_full_workflow_in_order()
    print("  ✅ full AG2 workflow order is correct")
    test_groupchat_retries_same_producer_after_critic_rejection()
    print("  ✅ critic rejection loops back to the same producer")
    test_research_query_builders_are_agent_specific()
    print("  ✅ agent-specific research query packs are targeted")
    test_collect_usage_summary_aggregates_agents()
    print("  ✅ usage and cost summaries aggregate across agents")
    test_extract_pipeline_data_and_pdf_generation()
    print("  ✅ extraction and PDF generation still work")
    test_extract_pipeline_data_rejects_legacy_payload_shapes()
    print("  ✅ legacy payload shapes are rejected instead of normalized")
    test_try_parse_json()
    print("  ✅ JSON extraction handles expected variants")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✅")
    print("=" * 60)


if __name__ == "__main__":
    main()
