import numpy as np

from dashboard.analysis.metrics import analyse, classify_trend
from dashboard.analysis.signals import PriceContext, Signal, VolumeSpike, evaluate


def test_uptrend_classification_and_near_high(trending_up):
    m = analyse(trending_up).metrics
    assert m["trend"] == "Uptrend"
    assert any("52-week high" in s["text"] for s in m["signals"])
    assert m["chg_1d"] > 0 and m["above_sma200"] is True


def test_downtrend_classification(trending_down):
    assert analyse(trending_down).metrics["trend"] == "Downtrend"


def test_classify_trend_without_200d():
    assert classify_trend(10, 9, None) == "Uptrend"
    assert classify_trend(10, None, None) == "n/a"


def test_series_lengths_align(trending_up):
    s = analyse(trending_up).series
    assert len(s["d"]) == len(s["c"]) == len(s["sma200"]) == len(s["rsi"]) == 260


def test_volume_spike_rule(frame):
    df = frame(np.linspace(10, 11, 60))
    df.iloc[-1, df.columns.get_loc("Volume")] = 5_000_000
    sigs = VolumeSpike(2.0).evaluate(PriceContext.from_frame(df))
    assert sigs and "Volume 5.0×" in sigs[0].text


def test_custom_rule_is_pluggable(trending_up):
    class AlwaysHello:
        def evaluate(self, ctx):
            return [Signal("info", "hello")]
    out = evaluate(PriceContext.from_frame(trending_up), [AlwaysHello()])
    assert out == [Signal("info", "hello")]
