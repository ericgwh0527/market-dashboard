"""Google News RSS adapter."""
from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone

from .base import NewsItem


class GoogleNewsProvider:
    URL = "https://news.google.com/rss/search?q={q}&hl=en-MY&gl=MY&ceid=MY:en"

    def __init__(self, parser=None):
        if parser is None:
            import feedparser
            parser = feedparser.parse
        self._parse = parser

    def search(self, query: str, limit: int = 8, days: int = 3) -> list[NewsItem]:
        url = self.URL.format(q=urllib.parse.quote(f"{query} when:{days}d"))
        try:
            feed = self._parse(url, agent="Mozilla/5.0 (market-dashboard)")
        except Exception:
            return []
        return [self.parse_entry(e) for e in feed.entries[:limit]]

    @staticmethod
    def parse_entry(e) -> NewsItem:
        title = e.get("title", "")
        src = e.get("source")
        src = src.get("title") if isinstance(src, dict) else None
        if src and title.endswith(" - " + src):     # Google appends " - Publisher"
            title = title[: -len(src) - 3]
        pub = None
        if e.get("published_parsed"):
            pub = datetime(*e["published_parsed"][:6], tzinfo=timezone.utc).isoformat()
        return {"title": title, "url": e.get("link"), "published": pub, "source": src or "Google News"}
