"""Signal rules.

Each rule is a small object with one job: look at a PriceContext and return
zero or more Signals. To add a signal, write a new class and add it to
DEFAULT_RULES; nothing else changes (open/closed principle).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

import pandas as pd

from . import indicators as ind


@dataclass(frozen=True)
class Signal:
    type: str   # "good" | "bad" | "warn" | "info" – drives colour/icon in the UI
    text: str

    def as_dict(self) -> dict:
        return {"type": self.type, "text": self.text}


@dataclass
class PriceContext:
    """Everything a rule may need, computed once per symbol."""
    close: pd.Series
    high: pd.Series
    low: pd.Series
    volume: pd.Series
    sma50: pd.Series
    sma200: pd.Series
    rsi: pd.Series
    macd_hist: pd.Series

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> "PriceContext":
        c = df["Close"]
        return cls(close=c, high=df["High"], low=df["Low"], volume=df["Volume"],
                   sma50=ind.sma(c, 50), sma200=ind.sma(c, 200),
                   rsi=ind.rsi(c), macd_hist=ind.macd(c)[2])

    @property
    def last(self) -> float:
        return float(self.close.iloc[-1])

    @property
    def high_52w(self) -> float:
        return float(self.high.iloc[-252:].max())

    @property
    def low_52w(self) -> float:
        return float(self.low.iloc[-252:].min())

    @property
    def volume_ratio(self) -> float | None:
        if len(self.volume) <= 21:
            return None
        avg = self.volume.iloc[-21:-1].mean()
        return float(self.volume.iloc[-1] / avg) if avg and avg > 0 else None


class SignalRule(Protocol):
    def evaluate(self, ctx: PriceContext) -> Iterable[Signal]: ...


# ---------------------------------------------------------------- rules
class RsiExtremes:
    def __init__(self, overbought: float = 70, oversold: float = 30):
        self.overbought, self.oversold = overbought, oversold

    def evaluate(self, ctx):
        r = ctx.rsi.iloc[-1]
        if pd.isna(r):
            return []
        if r >= self.overbought:
            return [Signal("warn", f"RSI {r:.0f} – overbought (ran up fast)")]
        if r <= self.oversold:
            return [Signal("info", f"RSI {r:.0f} – oversold (sold off hard)")]
        return []


class MovingAverageCross:
    """Golden / death cross of the 50- and 200-day averages within the lookback."""
    def __init__(self, lookback: int = 10):
        self.lookback = lookback

    def evaluate(self, ctx):
        diff = (ctx.sma50 - ctx.sma200).dropna()
        if len(diff) <= self.lookback:
            return []
        w = diff.iloc[-self.lookback:]
        if w.iloc[0] < 0 < w.iloc[-1]:
            return [Signal("good", "Golden cross – 50-day avg crossed above 200-day")]
        if w.iloc[0] > 0 > w.iloc[-1]:
            return [Signal("bad", "Death cross – 50-day avg crossed below 200-day")]
        return []


class MacdTurn:
    def evaluate(self, ctx):
        h = ctx.macd_hist
        if len(h) < 4:
            return []
        if h.iloc[-1] > 0 >= h.iloc[-3]:
            return [Signal("good", "MACD turned bullish (momentum improving)")]
        if h.iloc[-1] < 0 <= h.iloc[-3]:
            return [Signal("bad", "MACD turned bearish (momentum fading)")]
        return []


class NearYearExtremes:
    def __init__(self, tolerance: float = 0.01):
        self.tol = tolerance

    def evaluate(self, ctx):
        if ctx.last >= ctx.high_52w * (1 - self.tol):
            return [Signal("good", "At / near 52-week high")]
        if ctx.last <= ctx.low_52w * (1 + self.tol):
            return [Signal("bad", "At / near 52-week low")]
        return []


class VolumeSpike:
    def __init__(self, threshold: float = 2.0):
        self.threshold = threshold

    def evaluate(self, ctx):
        v = ctx.volume_ratio
        return [Signal("info", f"Volume {v:.1f}× the 20-day average")] if v and v >= self.threshold else []


class Sma200Break:
    def evaluate(self, ctx):
        s = ctx.sma200
        if len(s.dropna()) < 2:
            return []
        prev_above = ctx.close.iloc[-2] > s.iloc[-2]
        now_above = ctx.close.iloc[-1] > s.iloc[-1]
        if now_above and not prev_above:
            return [Signal("good", "Closed back above 200-day average")]
        if prev_above and not now_above:
            return [Signal("bad", "Fell below 200-day average")]
        return []


DEFAULT_RULES: list[SignalRule] = [
    RsiExtremes(), MovingAverageCross(), MacdTurn(), NearYearExtremes(), VolumeSpike(), Sma200Break(),
]


def evaluate(ctx: PriceContext, rules: Iterable[SignalRule] = DEFAULT_RULES) -> list[Signal]:
    return [sig for rule in rules for sig in rule.evaluate(ctx)]
