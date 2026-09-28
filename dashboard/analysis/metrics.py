"""Per-symbol metrics built from a daily OHLCV frame."""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from . import indicators as ind
from .signals import PriceContext, SignalRule, DEFAULT_RULES, evaluate

# trading-day lookbacks for the performance columns
PERIODS = {"chg_1d": 1, "chg_5d": 5, "chg_1m": 21, "chg_3m": 63, "chg_6m": 126, "chg_1y": 252}
SPARK_DAYS = 66
SERIES_DAYS = 260


def classify_trend(price: float, sma50: float | None, sma200: float | None) -> str:
    if sma50 and sma200:
        if price > sma50 > sma200:
            return "Uptrend"
        if price < sma50 < sma200:
            return "Downtrend"
        return "Mixed"
    if sma50:
        return "Uptrend" if price > sma50 else "Downtrend"
    return "n/a"


def _last(s: pd.Series):
    return None if not len(s) or pd.isna(s.iloc[-1]) else float(s.iloc[-1])


def ytd_change(close: pd.Series) -> float | None:
    year = close.index[-1].year
    before = close[close.index.year < year]
    base = before.iloc[-1] if len(before) else close[close.index.year == year].iloc[0]
    return ind.pct_change(close.iloc[-1], base)


@dataclass
class Analysis:
    metrics: dict           # goes into latest.json
    series: dict            # goes into series/<SYMBOL>.json


def analyse(df: pd.DataFrame, rules: list[SignalRule] = DEFAULT_RULES) -> Analysis:
    """df: daily OHLCV, ascending DatetimeIndex, no NaN closes."""
    ctx = PriceContext.from_frame(df)
    c = ctx.close
    last = ctx.last
    sma20, sma50, sma200 = _last(ind.sma(c, 20)), _last(ctx.sma50), _last(ctx.sma200)
    daily = c.pct_change().dropna()

    metrics = {
        "price": last,
        "prev_close": float(c.iloc[-2]) if len(c) > 1 else None,
        "date": c.index[-1].strftime("%Y-%m-%d"),
        **{k: (ind.pct_change(last, c.iloc[-n - 1]) if len(c) > n else None) for k, n in PERIODS.items()},
        "chg_ytd": ytd_change(c),
        "hi_52w": ctx.high_52w, "lo_52w": ctx.low_52w,
        "from_hi_52w": ind.pct_change(last, ctx.high_52w),
        "sma20": sma20, "sma50": sma50, "sma200": sma200,
        "above_sma50": (last > sma50) if sma50 else None,
        "above_sma200": (last > sma200) if sma200 else None,
        "rsi14": _last(ctx.rsi),
        "macd_hist": _last(ctx.macd_hist),
        "volume": float(ctx.volume.iloc[-1]),
        "vol_ratio": ctx.volume_ratio,
        "volatility_60d": float(daily.iloc[-60:].std() * math.sqrt(252) * 100) if len(daily) > 20 else None,
        "trend": classify_trend(last, sma50, sma200),
        "signals": [s.as_dict() for s in evaluate(ctx, rules)],
        "spark": [round(float(x), 4) for x in c.iloc[-SPARK_DAYS:]],
    }

    tail = df.iloc[-SERIES_DAYS:]
    lines = pd.DataFrame({"sma20": ind.sma(c, 20), "sma50": ctx.sma50, "sma200": ctx.sma200, "rsi": ctx.rsi}).loc[tail.index]
    series = {
        "d": [d.strftime("%Y-%m-%d") for d in tail.index],
        "o": tail["Open"].round(4).tolist(), "h": tail["High"].round(4).tolist(),
        "l": tail["Low"].round(4).tolist(), "c": tail["Close"].round(4).tolist(),
        "v": tail["Volume"].astype(float).tolist(),
        "sma20": lines["sma20"].round(4).tolist(), "sma50": lines["sma50"].round(4).tolist(),
        "sma200": lines["sma200"].round(4).tolist(), "rsi": lines["rsi"].round(2).tolist(),
    }
    return Analysis(metrics, series)
