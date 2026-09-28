"""Entry point: build the public market data (docs/data/).

This file is only the *composition root*: it picks concrete providers and wires
them into MarketPipeline. The logic lives in the `dashboard` package.

    python scripts/fetch_data.py
Env: GEMINI_API_KEY (optional), SESSION (optional: after-bursa / after-us)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.config import load_settings  # noqa: E402
from dashboard.news import NewsService  # noqa: E402
from dashboard.pipeline import MarketPipeline, TooLittleData  # noqa: E402
from dashboard.providers.base import NullSummarizer  # noqa: E402
from dashboard.providers.gemini import GeminiSummarizer  # noqa: E402
from dashboard.providers.google_news import GoogleNewsProvider  # noqa: E402
from dashboard.providers.yahoo import (YahooFundamentalsProvider, YahooNewsProvider,  # noqa: E402
                                       YahooPriceProvider)
from dashboard.storage import DataStore  # noqa: E402


def build_pipeline() -> MarketPipeline:
    settings = load_settings(ROOT / "config.json")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return MarketPipeline(
        settings=settings,
        prices=YahooPriceProvider(),
        fundamentals=YahooFundamentalsProvider(),
        news=NewsService(search=GoogleNewsProvider(), by_symbol=YahooNewsProvider()),
        summarizer=GeminiSummarizer(key, settings.gemini_model) if key else NullSummarizer(),
        store=DataStore(ROOT / "docs" / "data"),
    )


def main() -> int:
    try:
        build_pipeline().run(session=os.environ.get("SESSION") or None)
    except TooLittleData as e:
        print(f"Keeping previous data: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
