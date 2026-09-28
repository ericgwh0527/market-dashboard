import numpy as np
import pandas as pd

from dashboard.analysis import indicators as ind


def test_rsi_is_100_when_price_only_rises():
    s = pd.Series(np.arange(1, 40, dtype=float))
    assert ind.rsi(s).iloc[-1] == 100


def test_rsi_is_low_when_price_only_falls():
    s = pd.Series(np.arange(40, 1, -1, dtype=float))
    assert ind.rsi(s).iloc[-1] < 1


def test_sma_matches_manual_mean():
    s = pd.Series([1.0, 2, 3, 4, 5])
    assert ind.sma(s, 5).iloc[-1] == 3


def test_macd_histogram_positive_in_accelerating_uptrend():
    s = pd.Series(np.linspace(1, 10, 100) ** 2)
    assert ind.macd(s)[2].iloc[-1] > 0


def test_pct_change_handles_bad_input():
    assert abs(ind.pct_change(110, 100) - 10) < 1e-9
    assert ind.pct_change(1, 0) is None
    assert ind.pct_change(None, 5) is None
    assert ind.pct_change(float("nan"), 5) is None
