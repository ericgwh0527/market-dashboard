"""Interfaces the pipeline depends on (dependency inversion).

Swap Yahoo for another data source by writing a class with the same methods;
the pipeline and analysis code do not change.
"""
from __future__ import annotations

from typing import Protocol, TypedDict

import pandas as pd


class NewsItem(TypedDict, total=False):
    title: str
    url: str
    published: str | None   # ISO-8601
    source: str
    topic: str


class PriceProvider(Protocol):
    def history(self, symbols: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
        """Daily OHLCV per symbol: columns Open, High, Low, Close, Volume; ascending, tz-naive index."""


class FundamentalsProvider(Protocol):
    def fundamentals(self, symbol: str) -> dict | None:
        """Valuation facts (pe, div_yield %, market_cap, …) or None when unavailable."""


class NewsProvider(Protocol):
    def search(self, query: str, limit: int = 8, days: int = 3) -> list[NewsItem]: ...


class SymbolNewsProvider(Protocol):
    def for_symbol(self, symbol: str, limit: int = 6) -> list[NewsItem]: ...


class Summarizer(Protocol):
    name: str

    def summarize(self, brief: dict) -> str | None: ...


class NullSummarizer:
    """Used when no AI key is configured."""
    name = "none"

    def summarize(self, brief: dict) -> str | None:
        return None
