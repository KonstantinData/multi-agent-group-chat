"""Website fetching helpers."""
from __future__ import annotations

import html
import re
import urllib.request
from html.parser import HTMLParser


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        cleaned = " ".join(data.split())
        if cleaned:
            self._parts.append(cleaned)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _meta_description(html_text: str) -> str:
    match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        html_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return html.unescape(" ".join(match.group(1).split()))


def _title(html_text: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return html.unescape(" ".join(match.group(1).split()))


def fetch_website_snapshot(url: str, *, timeout: int = 8) -> dict[str, str | bool]:
    cleaned_url = str(url or "").strip()
    if not cleaned_url or "://" not in cleaned_url:
        return {
            "reachable": False,
            "url": cleaned_url,
            "title": "",
            "meta_description": "",
            "visible_text": "",
        }

    try:
        request = urllib.request.Request(
            cleaned_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LiquistoBot/1.0)"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            html_text = response.read(200000).decode("utf-8", errors="ignore")
    except Exception:
        return {
            "reachable": False,
            "url": cleaned_url,
            "title": "",
            "meta_description": "",
            "visible_text": "",
        }

    parser = _VisibleTextParser()
    parser.feed(html_text)
    visible_text = parser.get_text()[:4000]
    return {
        "reachable": True,
        "url": cleaned_url,
        "title": _title(html_text)[:300],
        "meta_description": _meta_description(html_text)[:500],
        "visible_text": visible_text,
    }
