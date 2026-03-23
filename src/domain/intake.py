"""Intake-side domain models."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class IntakeRequest:
    company_name: str
    web_domain: str
    language: str = "de"


@dataclass(slots=True)
class SupervisorBrief:
    submitted_company_name: str
    submitted_web_domain: str
    verified_company_name: str
    verified_legal_name: str
    name_confidence: str
    website_reachable: bool
    homepage_url: str
    page_title: str
    meta_description: str
    raw_homepage_excerpt: str
    normalized_domain: str
    industry_hint: str = "n/v"
    observations: list[str] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)

    @property
    def company_name(self) -> str:
        return self.verified_legal_name or self.verified_company_name or self.submitted_company_name

    @property
    def web_domain(self) -> str:
        return self.normalized_domain or self.submitted_web_domain
