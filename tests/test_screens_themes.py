from dashboard.analysis.screens import DEFAULT_SCREENS, Screen, run_screens
from dashboard.analysis.themes import aggregate_themes

ROWS = [
    {"symbol": "A", "market": "MY", "theme": "Banks", "trend": "Uptrend", "rsi14": 72, "from_hi_52w": -1,
     "vol_ratio": 2.1, "chg_1d": 1.0, "chg_1m": 3.0, "fundamentals": {"pe": 10, "div_yield": 5}},
    {"symbol": "B", "market": "MY", "theme": "Banks", "trend": "Downtrend", "rsi14": None, "from_hi_52w": None,
     "chg_1d": -3.0, "chg_1m": None, "fundamentals": None},
]


def test_screens_match_and_tolerate_missing_data():
    res = {s["id"]: s["symbols"] for s in run_screens(ROWS)}
    assert res["uptrend"] == ["A"] and res["downtrend"] == ["B"]
    assert res["overbought"] == ["A"] and res["value"] == ["A"] and res["vol_spike"] == ["A"]
    assert res["oversold"] == []


def test_new_screen_needs_no_other_changes():
    extra = Screen("all", "All", "every stock", lambda r: True)
    res = run_screens(ROWS, [*DEFAULT_SCREENS, extra])
    assert res[-1]["symbols"] == ["A", "B"]


def test_theme_average():
    t = aggregate_themes(ROWS)
    assert len(t) == 1 and t[0]["chg_1d"] == -1.0 and t[0]["chg_1m"] == 3.0 and t[0]["members"] == ["A", "B"]
