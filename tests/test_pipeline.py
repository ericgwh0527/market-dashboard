import numpy as np

from dashboard.config import Instrument, NewsQuery, Settings
from dashboard.news import NewsService
from dashboard.pipeline import MarketPipeline, TooLittleData
from dashboard.providers.base import NullSummarizer
from dashboard.storage import DataStore

import pytest

SETTINGS = Settings(
    indices=[Instrument("^KLSE", "FBM KLCI", group="Malaysia")],
    stocks=[Instrument("1155.KL", "Maybank", market="MY", theme="Banks"),
            Instrument("NVDA", "Nvidia", market="US", theme="AI chips")],
    news_queries=[NewsQuery("Bursa", "Bursa Malaysia")],
)


class FakePrices:
    def __init__(self, frames):
        self.frames = frames

    def history(self, symbols, period="2y"):
        return {s: self.frames[s] for s in symbols if s in self.frames}


class FakeFundamentals:
    def fundamentals(self, symbol):
        return {"pe": 12.0, "div_yield": 4.0}


class FakeNews:
    def search(self, query, limit=8, days=3):
        return [{"title": f"{query} rallies", "url": "https://x/1", "published": "2026-09-28T01:00:00+00:00", "source": "T"}]

    def for_symbol(self, symbol, limit=6):
        return [{"title": f"{symbol} news", "url": "https://x/2", "published": "2026-09-27T01:00:00Z", "source": "Y"}]


class FakeSummarizer:
    name = "Fake"

    def summarize(self, brief):
        assert brief["stocks"] and brief["market_headlines"]
        return "**Big picture** calm."


def pipeline(tmp_path, frame, summarizer=None, frames=None):
    frames = frames if frames is not None else {s: frame(np.linspace(10, 20, 300)) for s in ("^KLSE", "1155.KL", "NVDA")}
    news = FakeNews()
    return MarketPipeline(SETTINGS, FakePrices(frames), FakeFundamentals(), NewsService(news, news),
                          summarizer or NullSummarizer(), DataStore(tmp_path), log=lambda *_: None)


def test_pipeline_output_contract(tmp_path, frame):
    """The front end relies on these keys – changing them is a breaking change."""
    out = pipeline(tmp_path, frame, FakeSummarizer()).run(session="after-bursa")
    assert {"generated_at", "generated_at_myt", "session", "indices", "stocks", "themes",
            "screens", "market_news", "summary"} <= out.keys()
    s = out["stocks"][0]
    for k in ("symbol", "name", "market", "theme", "price", "chg_1d", "rsi14", "trend", "signals", "spark",
              "file", "fundamentals", "news", "hi_52w", "sma200", "vol_ratio"):
        assert k in s
    assert (tmp_path / s["file"]).exists()
    assert out["summary"]["model"] == "Fake"
    assert (tmp_path / "history" / "index.json").exists()
    assert list((tmp_path / "summaries").glob("*.md"))


def test_pipeline_refuses_to_overwrite_with_empty_run(tmp_path, frame):
    with pytest.raises(TooLittleData):
        pipeline(tmp_path, frame, frames={}).run()


def test_missing_symbol_keeps_previous_row(tmp_path, frame):
    pipeline(tmp_path, frame).run()
    frames = {s: frame(np.linspace(10, 20, 300)) for s in ("^KLSE", "1155.KL")}
    out = pipeline(tmp_path, frame, frames=frames).run()
    nv = next(s for s in out["stocks"] if s["symbol"] == "NVDA")
    assert nv["stale"] is True


def test_summary_falls_back_to_previous(tmp_path, frame):
    pipeline(tmp_path, frame, FakeSummarizer()).run()
    out = pipeline(tmp_path, frame).run()
    assert out["summary"]["stale"] is True
