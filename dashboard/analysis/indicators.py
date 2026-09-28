"""Technical indicators (pure functions over a price Series)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(close: pd.Series, n: int) -> pd.Series:
    return close.rolling(n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder's RSI (0-100)."""
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(dn != 0, 100.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Returns (macd line, signal line, histogram)."""
    line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig, line - sig


def pct_change(a, b) -> float | None:
    """(a / b - 1) * 100, or None when undefined."""
    try:
        if a is None or b is None or b == 0 or pd.isna(a) or pd.isna(b):
            return None
        return (float(a) / float(b) - 1) * 100
    except (TypeError, ValueError):
        return None
