"""Normalization helpers."""
from __future__ import annotations

from urllib.parse import urlparse


def normalize_domain(domain: str) -> str:
    raw = (domain or "").strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    hostname = parsed.netloc or parsed.path
    hostname = hostname.removeprefix("www.")
    return hostname.strip("/")


def homepage_url(domain: str) -> str:
    normalized = normalize_domain(domain)
    return f"https://{normalized}" if normalized else ""

