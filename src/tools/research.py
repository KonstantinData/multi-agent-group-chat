"""Backward-compatible research helpers."""
from __future__ import annotations

from src.research.search import build_buyer_queries as _build_buyer_queries
from src.research.search import build_company_queries as _build_company_queries
from src.research.search import build_market_queries as _build_industry_queries

__all__ = ["_build_buyer_queries", "_build_company_queries", "_build_industry_queries"]
