"""Latest quotes for the private holdings.

The portfolio job holds the passphrase, so it deliberately avoids heavy
third-party packages (yfinance, pandas, numpy): YahooChartQuotes uses only the
Python standard library. Everything here is silent – Actions logs are public and
must never name what you hold.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Callable, Protocol

from .valuation import Quote


class QuoteProvider(Protocol):
    def quotes(self, symbols: list[str]) -> dict[str, Quote]: ...


def parse_chart(body: dict) -> Quote | None:
    """Yahoo /v8/finance/chart response -> last close and the one before it."""
    try:
        res = body["chart"]["result"][0]
        closes = res["indicators"]["quote"][0]["close"]
        stamps = res["timestamp"]
    except (KeyError, IndexError, TypeError):
        return None
    points = [(t, c) for t, c in zip(stamps, closes) if c is not None]
    if not points:
        return None
    (t_last, last) = points[-1]
    prev = points[-2][1] if len(points) > 1 else None
    date = datetime.fromtimestamp(t_last, tz=timezone.utc).strftime("%Y-%m-%d")
    return Quote(float(last), float(prev) if prev is not None else None, date)


class YahooChartQuotes:
    URL = "https://query2.finance.yahoo.com/v8/finance/chart/{sym}?range=10d&interval=1d"
    HEADERS = {"User-Agent": "Mozilla/5.0 (market-dashboard)", "Accept": "application/json"}

    def __init__(self, fetch: Callable[[str], dict] | None = None, pause: float = 0.3, retries: int = 2):
        self._fetch = fetch or self._http_get
        self.pause, self.retries = pause, retries

    def quotes(self, symbols: list[str]) -> dict[str, Quote]:
        out = {}
        for s in symbols:
            for attempt in range(self.retries):
                try:
                    q = parse_chart(self._fetch(self.URL.format(sym=urllib.parse.quote(s, safe=""))))
                except Exception:          # silent on purpose (public logs)
                    q = None
                if q:
                    out[s] = q
                    break
                time.sleep(self.pause * (attempt + 1))
            time.sleep(self.pause)
        return out

    def _http_get(self, url: str) -> dict:
        req = urllib.request.Request(url, headers=self.HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
