"""Lightweight extraction helpers from website text and search results."""
from __future__ import annotations

import re


def extract_product_keywords(text: str) -> list[str]:
    candidates = re.findall(r"\b[A-Z][a-zA-Z0-9-]{3,}\b", text or "")
    keywords: list[str] = []
    for item in candidates:
        lowered = item.lower()
        if lowered in {"home", "about", "contact", "career", "careers"}:
            continue
        if item not in keywords:
            keywords.append(item)
        if len(keywords) >= 8:
            break
    return keywords


def infer_industry(title: str, description: str, text: str) -> str:
    haystack = " ".join([title or "", description or "", text or ""]).lower()
    if any(token in haystack for token in ["machinery", "gear", "transmission", "engineering"]):
        return "Mechanical Engineering"
    if any(token in haystack for token in ["software", "cloud", "platform", "saas"]):
        return "Software"
    if any(token in haystack for token in ["medical", "pharma", "health"]):
        return "Healthcare"
    if any(token in haystack for token in ["packaging", "plastics", "materials"]):
        return "Industrial Materials"
    return "n/v"


def summarize_visible_text(text: str, *, limit: int = 320) -> str:
    compact = " ".join((text or "").split())
    return compact[:limit].strip() or "n/v"


LEGAL_SUFFIXES = ("gmbh", "ag", "se", "inc", "corp", "corporation", "ltd", "llc", "sarl", "spa", "bv")

_TITLE_NOISE_PREFIX = re.compile(
    r"^(homepage|welcome\s+to|about|official\s+site|home\s+-\s+|startseite)\s*",
    re.IGNORECASE,
)


def _clean_title_chunk(chunk: str) -> str:
    """Strip common navigation prefixes that are not part of a company name."""
    return _TITLE_NOISE_PREFIX.sub("", chunk).strip(" -:,")


def infer_company_identity(submitted_name: str, title: str, description: str, text: str) -> dict[str, str]:
    """Infer canonical and legal company names from homepage signals."""
    submitted = " ".join((submitted_name or "").split()).strip()
    title_text = " ".join((title or "").replace("|", " ").split()).strip()
    description_text = " ".join((description or "").split()).strip()
    visible_text = " ".join((text or "").split()).strip()

    candidates: list[str] = []
    if title_text:
        candidates.extend(
            [
                _clean_title_chunk(chunk)
                for chunk in re.split(r"[|:·-]", title_text)
                if _clean_title_chunk(chunk)
            ]
        )
    if submitted:
        candidates.insert(0, submitted)

    verified_company_name = submitted or "n/v"
    verified_legal_name = "n/v"
    name_confidence = "low"

    submitted_tokens = {token.lower() for token in re.findall(r"[A-Za-z0-9]+", submitted)}
    for candidate in candidates:
        candidate_tokens = {token.lower() for token in re.findall(r"[A-Za-z0-9]+", candidate)}
        if submitted_tokens and candidate_tokens and submitted_tokens.intersection(candidate_tokens):
            verified_company_name = candidate
            name_confidence = "medium"
            break

    # Build a cleaned search text: strip noise prefixes from title before regex matching
    clean_title = _clean_title_chunk(title_text)
    legal_match = re.search(
        r"\b([A-Z][A-Za-z0-9&.,' -]{2,}?\s(?:GmbH|AG|SE|Inc\.?|Corp\.?|Corporation|Ltd\.?|LLC|SARL|SpA|BV))\b",
        " ".join(part for part in [clean_title, description_text, visible_text[:500]] if part),
    )
    if legal_match:
        verified_legal_name = " ".join(legal_match.group(1).split())
        verified_company_name = verified_legal_name
        name_confidence = "high"
    elif any(verified_company_name.lower().endswith(suffix) for suffix in LEGAL_SUFFIXES):
        verified_legal_name = verified_company_name
        name_confidence = "high" if verified_company_name.lower() == submitted.lower() else "medium"

    return {
        "verified_company_name": verified_company_name or "n/v",
        "verified_legal_name": verified_legal_name,
        "name_confidence": name_confidence,
    }
