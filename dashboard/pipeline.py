"""MarketPipeline: builds latest.json + series + history from injected providers."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .analysis.metrics import analyse
from .analysis.screens import DEFAULT_SCREENS, Screen, run_screens
from .analysis.signals import DEFAULT_RULES, SignalRule
from .analysis.themes import aggregate_themes
from .config import Instrument, Settings
from .news import NewsService
from .providers.base import FundamentalsProvider, PriceProvider, Summarizer
from .storage import DataStore

MYT = timezone(timedelta(hours=8))


class TooLittleData(RuntimeError):
    """Raised instead of overwriting good data with a mostly-empty run."""


def session_for(now_utc: datetime) -> str:
    return "after-bursa" if 8 <= now_utc.hour < 18 else "after-us"


@dataclass
class MarketPipeline:
    settings: Settings
    prices: PriceProvider
    fundamentals: FundamentalsProvider
    news: NewsService
    summarizer: Summarizer
    store: DataStore
    rules: list[SignalRule] = field(default_factory=lambda: list(DEFAULT_RULES))
    screens: list[Screen] = field(default_factory=lambda: list(DEFAULT_SCREENS))
    min_coverage: float = 0.5
    log: callable = print

    def run(self, now: datetime | None = None, session: str | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        now_myt = now.astimezone(MYT)
        session = session or session_for(now)
        prev = self.store.previous_latest()

        symbols = [i.symbol for i in self.settings.all_instruments]
        self.log(f"Downloading prices for {len(symbols)} symbols …")
        frames = self.prices.history(symbols)
        if len(frames) < len(symbols) * self.min_coverage:
            raise TooLittleData(f"only {len(frames)}/{len(symbols)} symbols downloaded")

        prev_rows = {r["symbol"]: r for r in prev.get("indices", []) + prev.get("stocks", [])}
        indices = [r for r in (self._row(i, frames, prev_rows) for i in self.settings.indices) if r]

        self.log("Fetching fundamentals …")
        stocks = []
        for inst in self.settings.stocks:
            row = self._row(inst, frames, prev_rows)
            if not row:
                continue
            if not row.get("stale"):
                row["fundamentals"] = self.fundamentals.fundamentals(inst.symbol) or (prev_rows.get(inst.symbol) or {}).get("fundamentals")
            stocks.append(row)

        self.log("Fetching news …")
        by_symbol = {s.symbol: s for s in self.settings.stocks}
        for row in stocks:
            row["news"] = self.news.for_stock(by_symbol[row["symbol"]])
        market_news = self.news.market(self.settings.news_queries)

        latest = {
            "generated_at": now.isoformat(timespec="seconds"),
            "generated_at_myt": now_myt.strftime("%a %d %b %Y, %I:%M %p MYT"),
            "session": session,
            "indices": indices,
            "stocks": stocks,
            "themes": aggregate_themes(stocks),
            "screens": run_screens(stocks, self.screens),
            "market_news": market_news,
            "summary": self._summary(indices, stocks, market_news, prev, latest_time=now_myt, session=session),
        }
        self.store.save_latest(latest)
        self.store.save_history(now_myt, session, self._snapshot(latest))
        self.log(f"Done: {len(indices)} indices, {len(stocks)} stocks, {len(market_news)} headlines, "
                 f"summary={'yes' if latest['summary'] and not latest['summary'].get('stale') else 'no'}")
        return latest

    # ------------------------------------------------------------ steps
    def _row(self, inst: Instrument, frames: dict, prev_rows: dict) -> dict | None:
        df = frames.get(inst.symbol)
        if df is None:
            old = prev_rows.get(inst.symbol)   # keep last known row so the UI doesn't lose it
            return {**old, "stale": True} if old else None
        a = analyse(df, self.rules)
        rel = self.store.save_series(inst.symbol, a.series)
        return {**inst.as_dict(), **a.metrics, "file": rel}

    def _summary(self, indices, stocks, market_news, prev, latest_time, session):
        brief = {
            "indices": [{k: i.get(k) for k in ("name", "price", "chg_1d", "chg_5d", "chg_1m", "trend")} for i in indices],
            "stocks": [{**{k: s.get(k) for k in ("name", "symbol", "market", "price", "chg_1d", "chg_5d", "chg_1m", "rsi14", "trend")},
                        "signals": [x["text"] for x in s.get("signals", [])],
                        "headlines": [n["title"] for n in s.get("news", [])[:2]]} for s in stocks],
            "market_headlines": [n["title"] for n in market_news[:15]],
        }
        try:
            text = self.summarizer.summarize(brief)
        except Exception as e:  # an AI hiccup must never break the data run
            print(f"summary failed: {type(e).__name__}", file=sys.stderr)
            text = None
        stamp = latest_time.strftime("%a %d %b %Y, %I:%M %p MYT")
        if text:
            self.store.save_summary(latest_time, session, stamp, text)
            return {"text": text, "model": self.summarizer.name, "generated_at_myt": stamp}
        return {**prev["summary"], "stale": True} if prev.get("summary") else None

    @staticmethod
    def _snapshot(latest: dict) -> dict:
        keys = ("symbol", "name", "price", "chg_1d", "chg_1m", "rsi14", "trend", "vol_ratio", "from_hi_52w")
        return {
            "generated_at": latest["generated_at"], "session": latest["session"],
            "rows": [{**{k: x.get(k) for k in keys}, "signals": [s["text"] for s in x.get("signals", [])]}
                     for x in latest["indices"] + latest["stocks"]],
            "top_headlines": [n["title"] for n in latest["market_news"][:10]],
        }
