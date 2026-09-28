"""Yahoo Finance adapters (via yfinance)."""
from __future__ import annotations

import contextlib
import io
import logging
import sys
import time
from datetime import datetime, timezone

import pandas as pd

from .base import NewsItem

OHLCV = ["Open", "High", "Low", "Close", "Volume"]


@contextlib.contextmanager
def silenced():
    """Swallow all yfinance output. Actions logs of a public repo are public, so this
    is used whenever private symbols (your holdings) are requested."""
    log = logging.getLogger("yfinance")
    was = log.disabled
    log.disabled = True
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            yield
    finally:
        log.disabled = was


class YahooPriceProvider:
    def __init__(self, retries: int = 3, min_rows: int = 30, quiet: bool = False, sleep=time.sleep):
        self.retries, self.min_rows, self.quiet, self._sleep = retries, min_rows, quiet, sleep

    def history(self, symbols: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
        ctx = silenced() if self.quiet else contextlib.nullcontext()
        with ctx:
            return self._download(symbols, period)

    def _download(self, symbols, period):
        import yfinance as yf
        out: dict[str, pd.DataFrame] = {}
        for attempt in range(self.retries):
            todo = [s for s in symbols if s not in out]
            if not todo:
                break
            try:
                raw = yf.download(todo, period=period, interval="1d", group_by="ticker",
                                  auto_adjust=False, threads=True, progress=False)
            except Exception as e:  # network / Yahoo hiccup – retry
                self._log(f"download attempt {attempt + 1} failed: {e}")
                self._sleep(5 * (attempt + 1))
                continue
            for s in todo:
                df = self._extract(raw, s)
                if df is not None:
                    out[s] = df
            if len(out) < len(symbols):
                self._sleep(3)
        missing = [s for s in symbols if s not in out]
        if missing:
            self._log(f"No price data for {len(missing)} symbol(s): {', '.join(missing)}")
        return out

    def _extract(self, raw: pd.DataFrame, symbol: str) -> pd.DataFrame | None:
        try:
            df = raw[symbol] if isinstance(raw.columns, pd.MultiIndex) else raw
            df = df[OHLCV].dropna(subset=["Close"]).copy()
        except (KeyError, TypeError):
            return None
        if len(df) < self.min_rows:
            return None
        df["Volume"] = df["Volume"].fillna(0)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df.sort_index()

    def _log(self, msg):
        if not self.quiet:
            print(msg, file=sys.stderr)


class YahooFundamentalsProvider:
    FIELDS = {
        "longName": "long_name", "sector": "sector", "industry": "industry", "currency": "currency",
        "marketCap": "market_cap", "trailingPE": "pe", "forwardPE": "forward_pe", "priceToBook": "pb",
        "dividendYield": "div_yield", "trailingEps": "eps", "profitMargins": "profit_margin",
        "revenueGrowth": "revenue_growth", "earningsGrowth": "earnings_growth", "returnOnEquity": "roe",
        "debtToEquity": "debt_to_equity", "beta": "beta", "targetMeanPrice": "target_price",
        "recommendationKey": "analyst_view", "numberOfAnalystOpinions": "analyst_count",
    }
    RATIOS_AS_PCT = ("profit_margin", "revenue_growth", "earnings_growth", "roe")

    def __init__(self, retries: int = 2, pause: float = 0.4, sleep=time.sleep):
        self.retries, self.pause, self._sleep = retries, pause, sleep

    def fundamentals(self, symbol: str) -> dict | None:
        import yfinance as yf
        for _ in range(self.retries):
            try:
                info = yf.Ticker(symbol).info or {}
                self._sleep(self.pause)
                return self.normalise(info) if info else None
            except Exception as e:
                print(f"info {symbol} failed: {e}", file=sys.stderr)
                self._sleep(2)
        return None

    @classmethod
    def normalise(cls, info: dict) -> dict:
        f = {out: info.get(src) for src, out in cls.FIELDS.items()}
        dy = f.get("div_yield")
        if isinstance(dy, (int, float)) and dy < 1:   # yfinance changed units across versions
            f["div_yield"] = dy * 100
        for k in cls.RATIOS_AS_PCT:
            if isinstance(f.get(k), (int, float)):
                f[k] = f[k] * 100
        ts = info.get("earningsTimestamp") or info.get("earningsTimestampStart")
        if isinstance(ts, (int, float)):
            f["next_earnings"] = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        return f


class YahooNewsProvider:
    def for_symbol(self, symbol: str, limit: int = 6) -> list[NewsItem]:
        import yfinance as yf
        try:
            items = yf.Ticker(symbol).news or []
        except Exception:
            return []
        return [x for x in (self.parse(n) for n in items) if x][:limit]

    @staticmethod
    def parse(n: dict) -> NewsItem | None:
        """Handles both the old flat and the newer {'content': {...}} yfinance shapes."""
        c = n.get("content") if isinstance(n.get("content"), dict) else n
        title = c.get("title")
        url = ((c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url") or c.get("link"))
        pub = c.get("pubDate") or c.get("displayTime")
        if not pub and c.get("providerPublishTime"):
            pub = datetime.fromtimestamp(c["providerPublishTime"], tz=timezone.utc).isoformat()
        src = (c.get("provider") or {}).get("displayName") or c.get("publisher") or "Yahoo Finance"
        return {"title": title, "url": url, "published": pub, "source": src} if title and url else None
