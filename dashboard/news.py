"""Combines news providers into the two feeds the dashboard shows."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from .config import Instrument, NewsQuery
from .providers.base import NewsItem, NewsProvider, SymbolNewsProvider


def dedupe(items: list[NewsItem]) -> list[NewsItem]:
    seen, out = set(), []
    for it in items:
        k = re.sub(r"\W+", "", (it.get("title") or "").lower())[:70]
        if k and k not in seen:
            seen.add(k)
            out.append(it)
    return out


def _ts(it: NewsItem) -> float:
    try:
        d = datetime.fromisoformat(str(it.get("published")).replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
    except ValueError:
        return 0.0


def newest_first(items: list[NewsItem]) -> list[NewsItem]:
    return sorted(items, key=_ts, reverse=True)


class NewsService:
    def __init__(self, search: NewsProvider, by_symbol: SymbolNewsProvider):
        self.search, self.by_symbol = search, by_symbol

    def for_stock(self, stock: Instrument, limit: int = 6) -> list[NewsItem]:
        items = self.by_symbol.for_symbol(stock.symbol, 5)
        # Yahoo's Bursa coverage is thin – top up with Google News
        if stock.market == "MY" or len(items) < 3:
            q = f'"{stock.name}" Bursa' if stock.market == "MY" else f"{stock.name} stock"
            items += self.search.search(q, 5, days=7)
        return newest_first(dedupe(items))[:limit]

    def market(self, queries: list[NewsQuery], limit: int = 40) -> list[NewsItem]:
        items = [{**it, "topic": q.label} for q in queries for it in self.search.search(q.query, 8, days=2)]
        return newest_first(dedupe(items))[:limit]
