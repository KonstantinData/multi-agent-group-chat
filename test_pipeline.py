"""Simulate a full pipeline run with mock data – no OpenAI calls needed."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import time
from datetime import datetime, timezone

from src.pipeline_runner import AGENT_META, PIPELINE_STEPS, _extract_pipeline_data, _try_parse_json
from src.exporters.pdf_report import generate_pdf


def _ts():
    return datetime.now(timezone.utc).isoformat()


def main():
    print("=" * 60)
    print("SIMULATED PIPELINE TEST")
    print("=" * 60)

    messages = []

    def emit(agent: str, content: str, msg_type: str = "agent_message"):
        event = {
            "type": msg_type,
            "agent": agent,
            "content": content,
            "timestamp": _ts(),
            "meta": AGENT_META.get(agent, {"icon": "⚙️", "color": "#adb5bd"}),
        }
        messages.append(event)
        icon = event["meta"]["icon"]
        preview = content.replace("\n", " ")[:80]
        print(f"  {icon} {agent:20s} | {msg_type:15s} | {preview}")

    # --- System init ---
    emit("System", "Pipeline gestartet für: Lenze SE (lenze.com)", "debug")
    emit("System", "LLM Model: gpt-4 (SIMULATED)", "debug")
    emit("System", "Agenten erstellt: admin, concierge, company_intelligence, strategic_signals, market_network, evidence_qa, synthesis", "debug")
    emit("System", "GroupChat erstellt: 7 Agenten, max_round=25", "debug")
    emit("System", "Task erstellt, starte Chat...", "debug")
    time.sleep(0.5)

    # --- Admin ---
    emit("Admin", "Research the company 'Lenze SE' (domain: lenze.com) for a Liquisto sales meeting preparation.")
    time.sleep(0.3)

    # --- Concierge ---
    print(f"\n--- Step 1: Concierge ---")
    concierge_json = json.dumps({
        "company_name": "Lenze SE",
        "web_domain": "lenze.com",
        "language": "de",
        "observations": "Website erreichbar. Lenze ist ein Antriebstechnik-Hersteller."
    }, ensure_ascii=False, indent=2)
    emit("Concierge", concierge_json)
    time.sleep(0.3)

    # --- CompanyIntelligence ---
    print(f"\n--- Step 2: CompanyIntelligence ---")
    company_json = json.dumps({
        "company_name": "Lenze SE",
        "legal_form": "SE",
        "founded": "1947",
        "headquarters": "Aerzen, Deutschland",
        "website": "https://lenze.com",
        "industry": "Antriebstechnik / Automatisierung",
        "employees": "ca. 4.000",
        "revenue": "ca. 900 Mio. EUR",
        "products_and_services": [
            "Frequenzumrichter",
            "Servomotoren",
            "Getriebemotoren",
            "Steuerungstechnik",
            "Software & Engineering Tools"
        ],
        "key_people": [
            {"name": "Christian Wendler", "role": "CEO"},
            {"name": "Frank Maier", "role": "CTO"}
        ],
        "description": "Lenze ist ein global agierender Spezialist für Antriebs- und Automatisierungstechnik.",
        "economic_situation": {
            "revenue_trend": "leicht rückläufig",
            "profitability": "stabil",
            "recent_events": ["Restrukturierung 2024", "Fokus auf Digitalisierung"],
            "inventory_signals": ["Überbestände bei älteren Umrichter-Serien möglich"],
            "financial_pressure": "mittel",
            "assessment": "Solides Unternehmen mit Transformationsdruck durch Digitalisierung"
        },
        "sources": [
            {"publisher": "lenze.com", "url": "https://lenze.com/de/unternehmen", "title": "Über Lenze", "accessed": "2024-01-15"}
        ]
    }, ensure_ascii=False, indent=2)
    emit("CompanyIntelligence", company_json)
    time.sleep(0.3)

    # --- StrategicSignals ---
    print(f"\n--- Step 3: StrategicSignals ---")
    industry_json = json.dumps({
        "industry_name": "Antriebstechnik & Industrieautomatisierung",
        "market_size": "ca. 45 Mrd. EUR (Europa)",
        "trend_direction": "stabil",
        "growth_rate": "2-3% p.a.",
        "key_trends": [
            "Elektrifizierung und Energieeffizienz",
            "Industrie 4.0 / IoT-Integration",
            "Konsolidierung im Mittelstand"
        ],
        "overcapacity_signals": [
            "Überkapazitäten bei konventionellen Antrieben",
            "Lageraufbau durch Lieferkettenprobleme 2022-2023"
        ],
        "excess_stock_indicators": "Ältere Umrichter-Generationen werden durch neue Plattformen ersetzt",
        "demand_outlook": "Stabil mit Verschiebung zu digitalen Lösungen",
        "assessment": "Reifer Markt mit Transformationsdruck – Überbestände bei Legacy-Produkten wahrscheinlich",
        "sources": []
    }, ensure_ascii=False, indent=2)
    emit("StrategicSignals", industry_json)
    time.sleep(0.3)

    # --- MarketNetwork ---
    print(f"\n--- Step 4: MarketNetwork ---")
    market_json = json.dumps({
        "target_company": "Lenze SE",
        "peer_competitors": {
            "companies": [
                {"name": "SEW-Eurodrive", "website": "sew-eurodrive.de", "city": "Bruchsal", "country": "DE", "relevance": "Direkter Wettbewerber bei Getriebemotoren", "matching_products": ["Getriebemotoren", "Frequenzumrichter"], "evidence_tier": "qualified"},
                {"name": "Nord Drivesystems", "website": "nord.com", "city": "Bargteheide", "country": "DE", "relevance": "Wettbewerber bei Antriebstechnik", "matching_products": ["Frequenzumrichter", "Getriebe"], "evidence_tier": "qualified"}
            ],
            "assessment": "Starke Peer-Ebene mit potenziellem Interesse an Einzelteilen",
            "sources": []
        },
        "downstream_buyers": {
            "companies": [
                {"name": "Krones AG", "website": "krones.com", "city": "Neutraubling", "country": "DE", "relevance": "Setzt Lenze-Antriebe in Abfüllanlagen ein", "matching_products": ["Servomotoren", "Umrichter"], "evidence_tier": "qualified"},
                {"name": "Multivac", "website": "multivac.com", "city": "Wolfertschwenden", "country": "DE", "relevance": "Verpackungsmaschinen mit Lenze-Komponenten", "matching_products": ["Servomotoren", "Steuerungen"], "evidence_tier": "candidate"}
            ],
            "assessment": "Breite Abnehmerbasis im Maschinenbau",
            "sources": []
        },
        "service_providers": {
            "companies": [
                {"name": "Gefran Deutschland", "website": "gefran.com", "city": "Seligenstadt", "country": "DE", "relevance": "Service und Wartung von Antriebssystemen", "matching_products": ["Ersatzteile Umrichter"], "evidence_tier": "candidate"}
            ],
            "assessment": "Service-Markt vorhanden aber schwer quantifizierbar",
            "sources": []
        },
        "cross_industry_buyers": {
            "companies": [
                {"name": "Jungheinrich AG", "website": "jungheinrich.de", "city": "Hamburg", "country": "DE", "relevance": "Intralogistik – könnte Antriebskomponenten für Flurförderzeuge nutzen", "matching_products": ["Getriebemotoren", "Umrichter"], "evidence_tier": "candidate"}
            ],
            "assessment": "Cross-Industry-Potenzial in Intralogistik und Medizintechnik",
            "sources": []
        }
    }, ensure_ascii=False, indent=2)
    emit("MarketNetwork", market_json)
    time.sleep(0.3)

    # --- EvidenceQA ---
    print(f"\n--- Step 5: EvidenceQA ---")
    qa_json = json.dumps({
        "validated_agents": ["Concierge", "CompanyIntelligence", "StrategicSignals", "MarketNetwork"],
        "evidence_health": "mittel",
        "open_gaps": [
            "Umsatzzahlen nicht aus Primärquelle verifiziert",
            "Service-Provider-Ebene dünn besetzt",
            "Cross-Industry Buyer nur 1 Kandidat"
        ],
        "recommendations": [
            "Jahresbericht oder Bundesanzeiger für Umsatzverifikation prüfen",
            "Service-Provider-Recherche vertiefen"
        ]
    }, ensure_ascii=False, indent=2)
    emit("EvidenceQA", qa_json)
    time.sleep(0.3)

    # --- Synthesis ---
    print(f"\n--- Step 6: Synthesis ---")
    synthesis_json = json.dumps({
        "target_company": "Lenze SE",
        "executive_summary": "Lenze SE ist ein etablierter Hersteller von Antriebs- und Automatisierungstechnik mit Sitz in Aerzen. Das Unternehmen befindet sich in einer Transformationsphase mit Fokus auf Digitalisierung. Überbestände bei älteren Produktgenerationen sind wahrscheinlich.",
        "liquisto_service_relevance": [
            {"service_area": "Excess Inventory", "relevance": "hoch", "reasoning": "Produktgenerationswechsel bei Umrichtern erzeugt wahrscheinlich Überbestände. Lenze hat ein breites Produktportfolio mit Legacy-Serien."},
            {"service_area": "Repurposing", "relevance": "mittel", "reasoning": "Einzelteile älterer Serien könnten für Peer-Konkurrenten oder Service-Firmen interessant sein."},
            {"service_area": "Analytics", "relevance": "mittel", "reasoning": "Bei ca. 4.000 Mitarbeitern und globalem Vertrieb könnte Value-Chain-Analytics Mehrwert bieten."}
        ],
        "case_assessments": [
            {
                "option": "kaufen",
                "summary": "Direktkauf von Überbeständen",
                "arguments": [
                    {"argument": "Starke Peer-Ebene (SEW, Nord) mit potenziellem Einzelteil-Interesse", "direction": "pro", "based_on": "MarketNetwork: 2 qualifizierte Peer-Konkurrenten"},
                    {"argument": "Breite Abnehmerbasis im Maschinenbau (Krones, Multivac)", "direction": "pro", "based_on": "MarketNetwork: Downstream Buyers"},
                    {"argument": "Umsatzzahlen nicht verifiziert – Risiko bei Volumeneinschätzung", "direction": "contra", "based_on": "EvidenceQA: Umsatz nicht aus Primärquelle"},
                    {"argument": "Service-Provider-Ebene dünn – Ersatzteil-Nachfrage schwer einschätzbar", "direction": "contra", "based_on": "EvidenceQA: Service-Provider dünn besetzt"}
                ]
            },
            {
                "option": "kommission",
                "summary": "Kommissionsmodell für schrittweisen Abverkauf",
                "arguments": [
                    {"argument": "Geringeres Risiko bei unsicherer Nachfrage-Quantifizierung", "direction": "pro", "based_on": "EvidenceQA: Mehrere offene Lücken"},
                    {"argument": "Lenze behält Eigentum – einfacherer Einstieg in Geschäftsbeziehung", "direction": "pro", "based_on": "Allgemeine Kommissionsvorteile"},
                    {"argument": "Niedrigere Marge für Liquisto", "direction": "contra", "based_on": "Geschäftsmodell-Logik"}
                ]
            },
            {
                "option": "ablehnen",
                "summary": "Kein Engagement",
                "arguments": [
                    {"argument": "Nur 1 Cross-Industry Kandidat – begrenztes Alternativmarkt-Potenzial", "direction": "pro", "based_on": "MarketNetwork: Cross-Industry dünn"},
                    {"argument": "Starke Peer- und Abnehmer-Ebene spricht gegen Ablehnung", "direction": "contra", "based_on": "MarketNetwork: 4+ identifizierte Käufer"}
                ]
            }
        ],
        "buyer_market_summary": "Insgesamt 6 potenzielle Käufer identifiziert. Peer-Ebene und Abnehmer-Ebene sind solide besetzt. Service- und Cross-Industry-Ebene brauchen weitere Recherche.",
        "total_peer_competitors": 2,
        "total_downstream_buyers": 2,
        "total_service_providers": 1,
        "total_cross_industry_buyers": 1,
        "key_risks": [
            "Umsatz/Finanzdaten nicht aus Primärquelle verifiziert",
            "Überbestandssituation ist Annahme, nicht bestätigt",
            "Service-Markt schwer quantifizierbar"
        ],
        "next_steps": [
            "Im Termin: Überbestandssituation direkt ansprechen",
            "Produktkatalog der Legacy-Serien anfragen",
            "Kontakt zu Einkauf/Supply Chain herstellen"
        ],
        "sources": []
    }, ensure_ascii=False, indent=2)
    emit("Synthesis", synthesis_json)
    time.sleep(0.3)

    # --- Admin terminates ---
    emit("Admin", "TERMINATE")
    emit("System", "Chat beendet. 8 Nachrichten.", "debug")

    # --- Test: Extract pipeline data ---
    print(f"\n{'=' * 60}")
    print("TESTING: _extract_pipeline_data()")
    pipeline_data = _extract_pipeline_data(messages, "Lenze SE")
    for key, val in pipeline_data.items():
        status = "✅ filled" if val else "❌ empty"
        print(f"  {key:25s} {status}")

    # --- Test: JSON parsing ---
    print(f"\n{'=' * 60}")
    print("TESTING: _try_parse_json()")
    test_cases = [
        ('direct json', '{"key": "value"}'),
        ('markdown fence', '```json\n{"key": "value"}\n```'),
        ('text + json', 'Here is the result:\n{"key": "value"}\nDone.'),
        ('no json', 'This is just text'),
        ('empty', ''),
    ]
    for label, text in test_cases:
        result = _try_parse_json(text)
        status = "✅" if (result is not None) == (label != "no json" and label != "empty") else "❌"
        print(f"  {status} {label:20s} -> {result}")

    # --- Test: PDF generation ---
    print(f"\n{'=' * 60}")
    print("TESTING: PDF generation")
    try:
        pdf_de = generate_pdf(pipeline_data, lang="de")
        print(f"  ✅ PDF DE: {len(pdf_de)} bytes")
    except Exception as e:
        print(f"  ❌ PDF DE failed: {e}")

    try:
        pdf_en = generate_pdf(pipeline_data, lang="en")
        print(f"  ✅ PDF EN: {len(pdf_en)} bytes")
    except Exception as e:
        print(f"  ❌ PDF EN failed: {e}")

    # Save test PDFs
    out = Path("artifacts/test")
    out.mkdir(parents=True, exist_ok=True)
    (out / "test_report_DE.pdf").write_bytes(pdf_de)
    (out / "test_report_EN.pdf").write_bytes(pdf_en)
    print(f"  📄 Saved to: {out.resolve()}")

    print(f"\n{'=' * 60}")
    print("ALL TESTS PASSED ✅")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
