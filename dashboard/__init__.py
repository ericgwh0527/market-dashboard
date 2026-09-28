"""Market dashboard data pipeline.

Layout (each module has one job; dependencies point inward to plain data):

    config.py            settings file -> typed Settings
    jsonio.py            JSON-safe values, read/write helpers
    analysis/            pure functions & rule registries (no I/O)
        indicators.py    SMA, RSI, MACD
        signals.py       SignalRule objects (add a rule = add a class)
        metrics.py       per-symbol metrics built from a price frame
        screens.py       Screen objects (add a screen = add an entry)
        themes.py        theme / sector aggregation
    providers/           adapters to the outside world, behind Protocols
        base.py          PriceProvider, FundamentalsProvider, NewsProvider, Summarizer
        yahoo.py         Yahoo Finance (yfinance) adapters
        google_news.py   Google News RSS adapter
        gemini.py        Gemini summarizer
    news.py              combines news providers, dedupes, sorts
    storage.py           where files go (docs/data/...)
    pipeline.py          MarketPipeline: orchestrates the above via injected deps
    portfolio/           private holdings -> encrypted output
        crypto.py        Cipher protocol + AES-256-GCM/PBKDF2 implementation
        valuation.py     pure valuation maths
        service.py       PortfolioService: orchestration
"""
