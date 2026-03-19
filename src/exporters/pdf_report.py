"""PDF report generator for Liquisto Market Intelligence briefings."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from fpdf import FPDF


# --- Translations ---

_T = {
    "de": {
        "title": "Liquisto Market Intelligence Briefing",
        "generated": "Erstellt am",
        "exec_summary": "Executive Summary",
        "company_profile": "Firmenprofil",
        "field_company": "Unternehmen",
        "field_legal_form": "Rechtsform",
        "field_founded": "Gegründet",
        "field_hq": "Hauptsitz",
        "field_website": "Website",
        "field_industry": "Branche",
        "field_employees": "Mitarbeiter",
        "field_revenue": "Umsatz",
        "field_products": "Produkte & Dienstleistungen",
        "field_key_people": "Schlüsselpersonen",
        "economic_situation": "Wirtschaftslage",
        "field_revenue_trend": "Umsatztrend",
        "field_profitability": "Profitabilität",
        "field_financial_pressure": "Finanzdruck",
        "field_assessment": "Einschätzung",
        "field_recent_events": "Aktuelle Ereignisse",
        "field_inventory_signals": "Bestandssignale",
        "industry_analysis": "Branchenanalyse",
        "field_market_size": "Marktgröße",
        "field_trend": "Trendrichtung",
        "field_growth": "Wachstumsrate",
        "field_demand": "Nachfrageausblick",
        "field_overcapacity": "Überkapazitätssignale",
        "field_excess_stock": "Überschussbestand-Indikatoren",
        "field_key_trends": "Schlüsseltrends",
        "buyer_network": "Käufernetzwerk",
        "tier_peers": "Peer-Konkurrenten",
        "tier_downstream": "Abnehmer",
        "tier_service": "Service-Anbieter",
        "tier_cross": "Cross-Industry Käufer",
        "evidence_qa": "Evidenz-Qualitätsprüfung",
        "field_evidence_health": "Evidenzqualität",
        "field_open_gaps": "Offene Lücken",
        "field_recommendations": "Empfehlungen",
        "liquisto_relevance": "Liquisto Service-Relevanz",
        "case_assessment": "Einschätzung je Option",
        "option_kaufen": "Kaufen",
        "option_kommission": "Kommission",
        "option_ablehnen": "Ablehnen",
        "pro": "PRO",
        "contra": "CONTRA",
        "based_on": "Basierend auf",
        "buyer_summary": "Käufermarkt-Zusammenfassung",
        "risks": "Risiken",
        "next_steps": "Nächste Schritte",
        "sources": "Quellen",
        "no_data": "Keine Daten verfügbar",
    },
    "en": {
        "title": "Liquisto Market Intelligence Briefing",
        "generated": "Generated on",
        "exec_summary": "Executive Summary",
        "company_profile": "Company Profile",
        "field_company": "Company",
        "field_legal_form": "Legal Form",
        "field_founded": "Founded",
        "field_hq": "Headquarters",
        "field_website": "Website",
        "field_industry": "Industry",
        "field_employees": "Employees",
        "field_revenue": "Revenue",
        "field_products": "Products & Services",
        "field_key_people": "Key People",
        "economic_situation": "Economic Situation",
        "field_revenue_trend": "Revenue Trend",
        "field_profitability": "Profitability",
        "field_financial_pressure": "Financial Pressure",
        "field_assessment": "Assessment",
        "field_recent_events": "Recent Events",
        "field_inventory_signals": "Inventory Signals",
        "industry_analysis": "Industry Analysis",
        "field_market_size": "Market Size",
        "field_trend": "Trend Direction",
        "field_growth": "Growth Rate",
        "field_demand": "Demand Outlook",
        "field_overcapacity": "Overcapacity Signals",
        "field_excess_stock": "Excess Stock Indicators",
        "field_key_trends": "Key Trends",
        "buyer_network": "Buyer Network",
        "tier_peers": "Peer Competitors",
        "tier_downstream": "Downstream Buyers",
        "tier_service": "Service Providers",
        "tier_cross": "Cross-Industry Buyers",
        "evidence_qa": "Evidence Quality Review",
        "field_evidence_health": "Evidence Health",
        "field_open_gaps": "Open Gaps",
        "field_recommendations": "Recommendations",
        "liquisto_relevance": "Liquisto Service Relevance",
        "case_assessment": "Case Assessment per Option",
        "option_kaufen": "Buy",
        "option_kommission": "Commission",
        "option_ablehnen": "Decline",
        "pro": "PRO",
        "contra": "CONTRA",
        "based_on": "Based on",
        "buyer_summary": "Buyer Market Summary",
        "risks": "Risks",
        "next_steps": "Next Steps",
        "sources": "Sources",
        "no_data": "No data available",
    },
}


class _ReportPDF(FPDF):
    def __init__(self, lang: str = "de"):
        super().__init__()
        self.lang = lang
        self.t = _T.get(lang, _T["en"])
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, self.t["title"], align="R", new_x="LMARGIN", new_y="NEXT")
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"{self.page_no()}/{{nb}}", align="C")

    def section_title(self, title: str):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(0, 51, 102)
        self.ln(6)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def sub_title(self, title: str):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(0, 0, 0)
        self.ln(3)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def field(self, label: str, value: str):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(60, 60, 60)
        self.cell(55, 6, f"{label}:")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 6, _safe(value))
        self.ln(1)

    def body_text(self, text: str):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 5, _safe(text))
        self.ln(2)

    def bullet(self, text: str):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(0, 0, 0)
        self.cell(6, 5, "-")
        self.multi_cell(0, 5, _safe(text))
        self.ln(1)

    def tag(self, label: str, color: tuple[int, int, int] = (0, 102, 51)):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*color)
        self.cell(0, 5, label, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)


def _safe(value: Any) -> str:
    text = str(value or "n/v").strip()
    # Replace characters that latin-1 can't encode
    replacements = {
        "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u2022": "-",
        "\u20ac": "EUR", "\u00df": "ss",
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _get(data: dict, *keys, default="n/v") -> Any:
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current or default


def generate_pdf(pipeline_data: dict[str, Any], lang: str = "de") -> bytes:
    """Generate a PDF report from pipeline data. Returns PDF as bytes."""
    t = _T.get(lang, _T["en"])
    pdf = _ReportPDF(lang=lang)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title page
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(0, 51, 102)
    pdf.ln(30)
    pdf.cell(0, 15, t["title"], align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(80, 80, 80)
    company = _get(pipeline_data, "company_profile", "company_name")
    pdf.cell(0, 10, _safe(company), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 10)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.cell(0, 8, f"{t['generated']} {now}", align="C", new_x="LMARGIN", new_y="NEXT")

    # --- Executive Summary ---
    pdf.add_page()
    synthesis = pipeline_data.get("synthesis", {})
    pdf.section_title(t["exec_summary"])
    pdf.body_text(_get(synthesis, "executive_summary"))

    # --- Company Profile ---
    profile = pipeline_data.get("company_profile", {})
    pdf.section_title(t["company_profile"])
    pdf.field(t["field_company"], _get(profile, "company_name"))
    pdf.field(t["field_legal_form"], _get(profile, "legal_form"))
    pdf.field(t["field_founded"], _get(profile, "founded"))
    pdf.field(t["field_hq"], _get(profile, "headquarters"))
    pdf.field(t["field_website"], _get(profile, "website"))
    pdf.field(t["field_industry"], _get(profile, "industry"))
    pdf.field(t["field_employees"], _get(profile, "employees"))
    pdf.field(t["field_revenue"], _get(profile, "revenue"))

    products = _get(profile, "products_and_services", default=[])
    if products and isinstance(products, list):
        pdf.sub_title(t["field_products"])
        for p in products:
            pdf.bullet(str(p))

    people = _get(profile, "key_people", default=[])
    if people and isinstance(people, list):
        pdf.sub_title(t["field_key_people"])
        for person in people:
            if isinstance(person, dict):
                pdf.bullet(f"{person.get('name', '?')} – {person.get('role', '?')}")

    # Economic situation
    econ = _get(profile, "economic_situation", default={})
    if isinstance(econ, dict):
        pdf.sub_title(t["economic_situation"])
        pdf.field(t["field_revenue_trend"], _get(econ, "revenue_trend"))
        pdf.field(t["field_profitability"], _get(econ, "profitability"))
        pdf.field(t["field_financial_pressure"], _get(econ, "financial_pressure"))
        pdf.field(t["field_assessment"], _get(econ, "assessment"))
        for event in _get(econ, "recent_events", default=[]) or []:
            pdf.bullet(str(event))

    # --- Industry Analysis ---
    industry = pipeline_data.get("industry_analysis", {})
    pdf.section_title(t["industry_analysis"])
    pdf.field(t["field_industry"], _get(industry, "industry_name"))
    pdf.field(t["field_market_size"], _get(industry, "market_size"))
    pdf.field(t["field_trend"], _get(industry, "trend_direction"))
    pdf.field(t["field_growth"], _get(industry, "growth_rate"))
    pdf.field(t["field_demand"], _get(industry, "demand_outlook"))
    pdf.field(t["field_excess_stock"], _get(industry, "excess_stock_indicators"))
    pdf.field(t["field_assessment"], _get(industry, "assessment"))

    overcap = _get(industry, "overcapacity_signals", default=[])
    if overcap and isinstance(overcap, list):
        pdf.sub_title(t["field_overcapacity"])
        for s in overcap:
            pdf.bullet(str(s))

    trends = _get(industry, "key_trends", default=[])
    if trends and isinstance(trends, list):
        pdf.sub_title(t["field_key_trends"])
        for tr in trends:
            pdf.bullet(str(tr))

    # --- Buyer Network ---
    market = pipeline_data.get("market_network", {})
    pdf.section_title(t["buyer_network"])

    for tier_key, tier_label in [
        ("peer_competitors", t["tier_peers"]),
        ("downstream_buyers", t["tier_downstream"]),
        ("service_providers", t["tier_service"]),
        ("cross_industry_buyers", t["tier_cross"]),
    ]:
        tier = _get(market, tier_key, default={})
        if not isinstance(tier, dict):
            continue
        companies = tier.get("companies", [])
        pdf.sub_title(f"{tier_label} ({len(companies)})")
        assessment = tier.get("assessment", "")
        if assessment and assessment != "n/v":
            pdf.body_text(assessment)
        for buyer in companies[:10]:
            if isinstance(buyer, dict):
                name = buyer.get("name", "?")
                rel = buyer.get("relevance", "")
                loc = ", ".join(filter(None, [buyer.get("city"), buyer.get("country")]))
                line = f"{name}"
                if loc:
                    line += f" ({loc})"
                if rel:
                    line += f" – {rel}"
                pdf.bullet(line)

    # --- Evidence QA ---
    qa = pipeline_data.get("quality_review", {})
    if qa:
        pdf.section_title(t["evidence_qa"])
        pdf.field(t["field_evidence_health"], _get(qa, "evidence_health"))
        gaps = _get(qa, "open_gaps", default=[])
        if gaps and isinstance(gaps, list):
            pdf.sub_title(t["field_open_gaps"])
            for gap in gaps:
                pdf.bullet(str(gap))
        recs = _get(qa, "recommendations", default=[])
        if recs and isinstance(recs, list):
            pdf.sub_title(t["field_recommendations"])
            for rec in recs:
                pdf.bullet(str(rec))

    # --- Liquisto Service Relevance ---
    relevance = _get(synthesis, "liquisto_service_relevance", default=[])
    if relevance and isinstance(relevance, list):
        pdf.section_title(t["liquisto_relevance"])
        for item in relevance:
            if isinstance(item, dict):
                area = item.get("service_area", "?")
                rel = item.get("relevance", "?")
                reasoning = item.get("reasoning", "")
                color = {"hoch": (0, 128, 0), "mittel": (200, 150, 0), "niedrig": (180, 0, 0)}.get(
                    rel.lower(), (80, 80, 80)
                )
                pdf.tag(f"{area}: {rel}", color)
                if reasoning:
                    pdf.body_text(reasoning)

    # --- Case Assessment (Pro/Contra) ---
    assessments = _get(synthesis, "case_assessments", default=[])
    if assessments and isinstance(assessments, list):
        pdf.section_title(t["case_assessment"])
        for case in assessments:
            if not isinstance(case, dict):
                continue
            option = case.get("option", "?")
            option_label = {
                "kaufen": t["option_kaufen"],
                "kommission": t["option_kommission"],
                "ablehnen": t["option_ablehnen"],
            }.get(option.lower(), option)
            pdf.sub_title(option_label)
            summary = case.get("summary", "")
            if summary:
                pdf.body_text(summary)
            for arg in case.get("arguments", []):
                if not isinstance(arg, dict):
                    continue
                direction = arg.get("direction", "").upper()
                color = (0, 128, 0) if direction == "PRO" else (180, 0, 0)
                pdf.tag(f"  {direction}", color)
                pdf.body_text(f"  {arg.get('argument', '')}")
                based = arg.get("based_on", "")
                if based:
                    pdf.set_font("Helvetica", "I", 8)
                    pdf.set_text_color(100, 100, 100)
                    pdf.cell(0, 4, f"    {t['based_on']}: {_safe(based)}", new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(2)

    # --- Buyer Summary + Risks + Next Steps ---
    buyer_summary = _get(synthesis, "buyer_market_summary")
    if buyer_summary and buyer_summary != "n/v":
        pdf.section_title(t["buyer_summary"])
        pdf.body_text(buyer_summary)

    risks = _get(synthesis, "key_risks", default=[])
    if risks and isinstance(risks, list):
        pdf.section_title(t["risks"])
        for r in risks:
            pdf.bullet(str(r))

    steps = _get(synthesis, "next_steps", default=[])
    if steps and isinstance(steps, list):
        pdf.section_title(t["next_steps"])
        for s in steps:
            pdf.bullet(str(s))

    return pdf.output()
