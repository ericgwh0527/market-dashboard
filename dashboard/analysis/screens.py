"""Rules-based screens over the analysed watchlist.

A Screen is data + a predicate. To add one, append to DEFAULT_SCREENS.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

Row = dict  # one analysed stock as it appears in latest.json


@dataclass(frozen=True)
class Screen:
    id: str
    name: str
    why: str
    predicate: Callable[[Row], bool]

    def run(self, rows: Iterable[Row]) -> dict:
        hits = []
        for r in rows:
            try:
                if self.predicate(r):
                    hits.append(r["symbol"])
            except (TypeError, KeyError):
                continue   # missing data never matches
        return {"id": self.id, "name": self.name, "why": self.why, "symbols": hits}


def _f(r: Row, key: str):
    return (r.get("fundamentals") or {}).get(key)


DEFAULT_SCREENS: list[Screen] = [
    Screen("uptrend", "Healthy uptrend", "Price above 50-day and 200-day averages – the trend is up.",
           lambda r: r.get("trend") == "Uptrend"),
    Screen("near_high", "Near 52-week high", "Within 3% of the highest price of the past year – strong momentum.",
           lambda r: r["from_hi_52w"] > -3),
    Screen("oversold", "Oversold (RSI < 35)", "Sold off quickly; sometimes bounces, sometimes keeps falling.",
           lambda r: r["rsi14"] < 35),
    Screen("overbought", "Overbought (RSI > 70)", "Ran up fast; risk of a pullback or pause.",
           lambda r: r["rsi14"] > 70),
    Screen("vol_spike", "Unusual volume", "Traded ≥1.8× normal volume – something is happening.",
           lambda r: (r.get("vol_ratio") or 0) >= 1.8),
    Screen("value", "Lower P/E + dividend", "P/E under 15 and dividend yield over 3% – classic 'value' filter.",
           lambda r: 0 < _f(r, "pe") < 15 and (_f(r, "div_yield") or 0) > 3),
    Screen("downtrend", "Downtrend", "Below 50-day and 200-day averages – the trend is down.",
           lambda r: r.get("trend") == "Downtrend"),
]


def run_screens(rows: list[Row], screens: Iterable[Screen] = DEFAULT_SCREENS) -> list[dict]:
    return [s.run(rows) for s in screens]
