"""Source classification helpers."""
from __future__ import annotations

from urllib.parse import urlparse


def source_is_owned(url: str, domain: str) -> bool:
    hostname = (urlparse(url).netloc or "").removeprefix("www.")
    normalized_domain = domain.removeprefix("www.")
    return bool(hostname and normalized_domain and hostname.endswith(normalized_domain))


def score_source(url: str, domain: str) -> str:
    return "owned" if source_is_owned(url, domain) else "external"

