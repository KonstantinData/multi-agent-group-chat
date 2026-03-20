"""Lightweight web research tools for AG2 agents."""
from __future__ import annotations

from html import unescape
import os
import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlparse
from urllib.request import Request, urlopen


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.8,de;q=0.7",
}
REQUEST_TIMEOUT = 10
MAX_HTML_BYTES = 512_000
MAX_TOOL_CALLS = int(os.environ.get("PIPELINE_MAX_TOOL_CALLS", "24"))


def register_research_tools(agent: Any, tool_names: list[str] | None = None) -> None:
    """Register shared research tools on an AG2 agent."""
    tool_registry = {
        "check_domain": (
            "Fetch a company domain homepage and return reachability, page title, and a conservative visible-language guess.",
            check_domain,
        ),
        "web_search": (
            "Search the public web for recent sources. Optionally restrict to a site/domain and keep results compact.",
            web_search,
        ),
        "fetch_page": (
            "Fetch a webpage and return normalized title, final URL, excerpt, and language hints for grounding claims.",
            fetch_page,
        ),
        "company_source_pack": (
            "Run a small curated batch of company-profile searches across official and registry-style sources, returning deduplicated candidate links.",
            company_source_pack,
        ),
        "industry_source_pack": (
            "Run a small curated batch of industry searches derived from company name, industry hint, and product keywords.",
            industry_source_pack,
        ),
        "buyer_source_pack": (
            "Run a small curated batch of competitor, customer, service, and aftermarket searches derived from company name and product keywords.",
            buyer_source_pack,
        ),
    }

    selected_names = tool_names or list(tool_registry.keys())

    for name in selected_names:
        description, func = tool_registry[name]
        llm_tool = agent.register_for_llm(name=name, description=description)(func)
        agent.register_for_execution(name=name, description=description)(llm_tool)


def check_domain(domain: str, context_variables: Any = None) -> dict[str, Any]:
    """Check whether a domain is reachable and summarize the homepage conservatively."""
    budget_error = _consume_tool_budget(context_variables, "check_domain")
    if budget_error:
        return budget_error
    normalized = _normalize_domain(domain)
    fetch = fetch_page(normalized, max_chars=1200, context_variables=None)
    return {
        "requested_domain": domain,
        "resolved_url": fetch.get("final_url", normalized),
        "reachable": fetch.get("ok", False),
        "status": fetch.get("status"),
        "title": fetch.get("title", ""),
        "language_guess": fetch.get("language_guess", "unknown"),
        "excerpt": fetch.get("excerpt", ""),
    }


def web_search(query: str, site: str = "", max_results: int = 5, context_variables: Any = None) -> dict[str, Any]:
    """Search the public web via DuckDuckGo's HTML endpoint."""
    budget_error = _consume_tool_budget(context_variables, "web_search")
    if budget_error:
        return budget_error
    max_results = max(1, min(int(max_results), 8))
    scoped_query = query.strip()
    if site.strip():
        scoped_query = f"site:{site.strip()} {scoped_query}".strip()
    if not scoped_query:
        return {"query": query, "results": [], "error": "empty query"}

    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(scoped_query)}"
    try:
        html_text, _final_url, _status = _http_get_text(search_url)
    except Exception as exc:
        return {
            "query": scoped_query,
            "results": [],
            "error": str(exc),
        }

    results = _parse_duckduckgo_results(html_text, max_results=max_results)
    return {
        "query": scoped_query,
        "site": site.strip(),
        "results": results,
    }


def fetch_page(url: str, max_chars: int = 4000, context_variables: Any = None) -> dict[str, Any]:
    """Fetch a webpage and return compact normalized content."""
    budget_error = _consume_tool_budget(context_variables, "fetch_page")
    if budget_error:
        return budget_error
    normalized_url = _normalize_url(url)
    try:
        html_text, final_url, status = _http_get_text(normalized_url)
    except Exception as exc:
        return {
            "ok": False,
            "url": normalized_url,
            "final_url": normalized_url,
            "status": None,
            "title": "",
            "language_guess": "unknown",
            "excerpt": "",
            "error": str(exc),
        }

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    title = _normalize_whitespace(unescape(title_match.group(1))) if title_match else ""
    text = _html_to_text(html_text)
    excerpt = text[: max(200, min(int(max_chars), 6000))]
    return {
        "ok": True,
        "url": normalized_url,
        "final_url": final_url,
        "status": status,
        "title": title,
        "language_guess": _detect_language(html_text, text),
        "excerpt": excerpt,
    }


def company_source_pack(
    company_name: str,
    domain: str = "",
    max_results: int = 10,
    context_variables: Any = None,
) -> dict[str, Any]:
    """Search a curated set of company-profile queries in one tool call."""
    budget_error = _consume_tool_budget(context_variables, "company_source_pack")
    if budget_error:
        return budget_error
    queries = _build_company_queries(company_name, domain)
    return _run_query_pack(queries, max_results=max_results)


def industry_source_pack(
    company_name: str,
    industry_hint: str = "",
    product_keywords: str = "",
    max_results: int = 10,
    context_variables: Any = None,
) -> dict[str, Any]:
    """Search a curated set of industry-signal queries in one tool call."""
    budget_error = _consume_tool_budget(context_variables, "industry_source_pack")
    if budget_error:
        return budget_error
    queries = _build_industry_queries(company_name, industry_hint, product_keywords)
    return _run_query_pack(queries, max_results=max_results)


def buyer_source_pack(
    company_name: str,
    product_keywords: str = "",
    domain: str = "",
    max_results: int = 10,
    context_variables: Any = None,
) -> dict[str, Any]:
    """Search a curated set of buyer-network queries in one tool call."""
    budget_error = _consume_tool_budget(context_variables, "buyer_source_pack")
    if budget_error:
        return budget_error
    queries = _build_buyer_queries(company_name, product_keywords, domain)
    return _run_query_pack(queries, max_results=max_results)


def _consume_tool_budget(context_variables: Any, tool_name: str) -> dict[str, Any] | None:
    if context_variables is None:
        return None

    used = int(context_variables.get("tool_calls_used", 0) or 0)
    if used >= MAX_TOOL_CALLS:
        return {
            "error": "tool budget exhausted",
            "tool_name": tool_name,
            "tool_calls_used": used,
            "max_tool_calls": MAX_TOOL_CALLS,
        }

    context_variables.set("tool_calls_used", used + 1)
    return None


def _run_query_pack(queries: list[str], max_results: int) -> dict[str, Any]:
    deduped_results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for query in queries[:6]:
        result = web_search(query=query, max_results=3)
        for item in result.get("results", []):
            url = item.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            deduped_results.append(
                {
                    "query": query,
                    "title": item.get("title", ""),
                    "url": url,
                    "snippet": item.get("snippet", ""),
                }
            )
            if len(deduped_results) >= max_results:
                break
        if len(deduped_results) >= max_results:
            break

    return {
        "queries": queries,
        "results": deduped_results,
    }


def _build_company_queries(company_name: str, domain: str) -> list[str]:
    clean_name = _normalize_whitespace(company_name)
    bare_domain = _bare_domain(domain)
    queries = [
        f'"{clean_name}" site:{bare_domain}' if bare_domain else f'"{clean_name}" official website',
        f'"{clean_name}" site:{bare_domain} company' if bare_domain else f'"{clean_name}" company profile',
        f'"{clean_name}" sustainability report',
        f'"{clean_name}" annual report',
        f'"{clean_name}" North Data',
        f'"{clean_name}" Dun & Bradstreet',
        f'"{clean_name}" Wikipedia',
    ]
    return _dedupe_queries(queries)


def _build_industry_queries(company_name: str, industry_hint: str, product_keywords: str) -> list[str]:
    clean_name = _normalize_whitespace(company_name)
    industry = _normalize_whitespace(industry_hint)
    keywords = _keyword_list(product_keywords, limit=3)
    focus = industry or "market"
    queries = [
        f'"{clean_name}" "{focus}"',
        f'"{focus}" market report 2023',
        f'"{focus}" demand outlook 2023',
        f'"{focus}" overcapacity 2023',
        f'"{focus}" excess inventory 2023',
    ]
    for keyword in keywords:
        queries.append(f'"{keyword}" market report 2023')
        queries.append(f'"{keyword}" overcapacity 2023')
    return _dedupe_queries(queries)


def _build_buyer_queries(company_name: str, product_keywords: str, domain: str) -> list[str]:
    clean_name = _normalize_whitespace(company_name)
    bare_domain = _bare_domain(domain)
    keywords = _keyword_list(product_keywords, limit=4)
    anchor_keyword = keywords[0] if keywords else clean_name
    queries = [
        f'"{clean_name}" customers',
        f'"{clean_name}" case study',
        f'"{clean_name}" service',
        f'"{anchor_keyword}" competitors',
        f'"{anchor_keyword}" aftermarket',
        f'"{anchor_keyword}" distributors',
    ]
    if bare_domain:
        queries.extend(
            [
                f'site:{bare_domain} customer',
                f'site:{bare_domain} application',
                f'site:{bare_domain} solution finder',
            ]
        )
    for keyword in keywords[1:]:
        queries.append(f'"{keyword}" competitors')
    return _dedupe_queries(queries)


def _http_get_text(url: str) -> tuple[str, str, int | None]:
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        raw = response.read(MAX_HTML_BYTES)
        charset = response.headers.get_content_charset() or "utf-8"
        text = raw.decode(charset, errors="replace")
        final_url = response.geturl()
        status = getattr(response, "status", None)
        return text, final_url, status


def _parse_duckduckgo_results(html_text: str, max_results: int) -> list[dict[str, str]]:
    anchor_pattern = re.compile(
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*>.*?</a>.*?<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>|'
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*>.*?</a>.*?<div[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</div>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    anchors = list(anchor_pattern.finditer(html_text))
    snippets = list(snippet_pattern.finditer(html_text))
    results: list[dict[str, str]] = []
    seen: set[str] = set()

    for index, anchor in enumerate(anchors):
        raw_url, raw_title = anchor.groups()
        resolved_url = _resolve_duckduckgo_url(raw_url)
        if not resolved_url or resolved_url in seen:
            continue
        seen.add(resolved_url)
        title = _html_to_text(raw_title)
        snippet = ""
        if index < len(snippets):
            snippet = _html_to_text(next(group for group in snippets[index].groups() if group))
        results.append(
            {
                "title": title,
                "url": resolved_url,
                "snippet": snippet,
            }
        )
        if len(results) >= max_results:
            break
    return results


def _resolve_duckduckgo_url(url: str) -> str:
    if url.startswith("//"):
        url = f"https:{url}"
    parsed = urlparse(url)
    if "duckduckgo.com" not in parsed.netloc:
        return url
    if parsed.path.startswith("/l/"):
        encoded = parse_qs(parsed.query).get("uddg", [""])[0]
        if encoded:
            return encoded
    return url


def _normalize_domain(domain: str) -> str:
    text = str(domain or "").strip()
    if not text:
        return ""
    if "://" not in text:
        return f"https://{text}"
    return text


def _normalize_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if not parsed.scheme:
        return f"https://{text}"
    return text


def _html_to_text(html_text: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html_text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript.*?>.*?</noscript>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    return _normalize_whitespace(text)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _bare_domain(value: str) -> str:
    text = _normalize_whitespace(value)
    if not text:
        return ""
    parsed = urlparse(_normalize_url(text))
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _keyword_list(value: str, limit: int = 4) -> list[str]:
    raw = [part.strip() for part in str(value or "").split(",")]
    return [item for item in raw if item][:limit]


def _dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for query in queries:
        normalized = _normalize_whitespace(query)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _detect_language(html_text: str, text: str) -> str:
    lang_match = re.search(r'\blang=["\']([a-zA-Z-]+)["\']', html_text, flags=re.IGNORECASE)
    if lang_match:
        lang = lang_match.group(1).lower()
        if lang.startswith("de"):
            return "de"
        if lang.startswith("en"):
            return "en"

    sample = f"{html_text[:1500]} {text[:1500]}".lower()
    german_markers = (" und ", " der ", " die ", " das ", " mit ", " impressum ", " datenschutz ")
    english_markers = (" and ", " the ", " with ", " privacy ", " contact ", " solutions ")
    german_hits = sum(marker in sample for marker in german_markers)
    english_hits = sum(marker in sample for marker in english_markers)
    if german_hits > english_hits:
        return "de"
    if english_hits > german_hits:
        return "en"
    return "unknown"
