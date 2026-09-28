# Market Dashboard · Bursa Malaysia + US

A free, serverless market dashboard for Bursa Malaysia and US stocks. It shows trends, technical signals, news, an optional AI daily brief, and an **end-to-end encrypted personal portfolio** inside a **public** repo.

**Live:** `https://<username>.github.io/market-dashboard/` · works on phone (add to home screen) and desktop.

## What it does

| Tab | What you get |
|---|---|
| **Overview** | KLCI, USD/MYR, S&P 500, Nasdaq, VIX, gold, oil and BTC tiles with sparklines; top movers; sector/theme heat; headlines; optional AI brief (Gemini) |
| **Watchlist** | 24 stocks (Bursa + US), filtered and sorted by return, RSI or distance from the 52-week high. Tap one for price/candle charts with 50-/200-day averages, RSI, fundamentals, signals and news |
| **Signals** | Rules-based screens (uptrend, near 52-week high, oversold, overbought, unusual volume, value) plus a plain-English glossary |
| **News** | Google News + Yahoo Finance headlines by topic and per stock |
| **Portfolio** | Your holdings with P/L, day change, allocation and value history, **decrypted in your browser** |

## Architecture

```mermaid
flowchart LR
  subgraph GH["GitHub Actions (cron, weekdays 17:35 & 05:40 MYT)"]
    F[MarketPipeline<br/>yfinance · RSS · Gemini] --> J[(docs/data/*.json)]
    P[PortfolioService<br/>AES-256-GCM] --> E[(portfolio.enc.json)]
  end
  PR[(Private repo<br/>holdings.json)] -- read-only token --> P
  J --> Pages[GitHub Pages<br/>static site]
  E --> Pages
  Pages --> B[Browser<br/>Web Crypto decrypt]
  J -. raw JSON .-> C[Claude<br/>Q&A / insights]
  PR -. private access .-> C
```

- **No server, no database, no cost.** Actions runs the Python job on a schedule and commits JSON. Pages serves the static front end (vanilla JS, [lightweight-charts](https://github.com/tradingview/lightweight-charts)).
- `docs/data/history/` keeps a compact snapshot per session, so trends over time can be analysed later.

## Security model (public repo, private holdings)

**Holdings privacy**
1. Real holdings live only in a **private** repo (`market-dashboard-private/holdings.json`).
2. The workflow reads it with a **fine-grained, read-only token** (`PRIVATE_REPO_TOKEN`, scoped to that one repo). The checkout is deleted before the commit step, and the commit step refuses to stage anything outside `docs/data/` or any file named like `holdings`.
3. `build_portfolio.py` values positions **in memory**. It writes no per-holding files, silences all library output and prints only exception *types*, because Actions logs of a public repo are public.
4. The result is encrypted with **AES-256-GCM**, using a key derived from `HOLDINGS_PASSPHRASE` via **PBKDF2-SHA256 (600k iterations)**, with a fresh IV every run. The plaintext is **padded to 8 KB blocks**, so the file size doesn't reveal how many positions you hold.
5. The browser decrypts locally with Web Crypto. "Keep unlocked" stores only a **non-extractable `CryptoKey`** in IndexedDB, never the passphrase, and it **expires after 30 days**.

**Website hardening**
- A strict **Content-Security-Policy** allows only this site's own scripts, styles, data and images, with no third-party requests (Google Fonts removed) and `connect-src 'self'`, so injected content couldn't send data elsewhere.
- Untrusted text (news titles, AI brief, Yahoo fields) is HTML-escaped. News links must be `http(s)`, and the AI brief goes through a tiny Markdown renderer that **cannot produce links, images or HTML**, which defends against prompt-injected `javascript:` links.
- Frame protection (the page refuses to run inside another site's iframe) and `no-referrer`.

**Pipeline / supply chain**
- Workflow token is read-only by default. Only the data job gets `contents: write`, and the token is **not persisted** in `.git/config`, so third-party Python code can't read it.
- GitHub Actions are pinned to **commit SHAs**. Python dependencies are pinned to exact versions **with hashes** (`scripts/requirements.lock`, installed with `--require-hashes`).
- Each secret is exposed only to the step that needs it. The Gemini key goes in a request header, never in a URL or log.
- CI fails if a `holdings.json` or anything shaped like an API key or token is committed.

**Residual risks (by design, know them)**
- The encrypted file is public, so it can be attacked **offline**. Its safety equals your passphrase: use 5+ random words and never reuse it.
- All `<username>.github.io/*` sites share one browser origin. Another Pages site of yours with untrusted scripts could use a remembered key. Only tick "keep unlocked" on your own devices, or use a custom domain.
- Anyone with access to your GitHub account controls everything. Turn on **2FA**, and give the fine-grained token an expiry.
- The watchlist, the data timestamps and the fact that a portfolio exists are public.
- The AI brief is generated from public headlines and can be wrong or manipulated. It's for learning, not advice.

To update pinned Python deps: `uv pip compile scripts/requirements.txt --python-version 3.12 --python-platform x86_64-manylinux_2_28 --generate-hashes -o scripts/requirements.lock` (same for `requirements-dev`).

## Setup

1. Fork or push this repo (it must be public for free Pages).
2. **Settings → Pages → Build and deployment:** *Deploy from a branch*, `main`, `/docs`.
3. **Actions → Update market data → Run workflow** fills in the first data.
4. *(Optional)* **AI brief:** get a free key at <https://aistudio.google.com/apikey> and add a repo secret named `GEMINI_API_KEY`.

### Portfolio setup (optional)

1. Create a **private** repo `market-dashboard-private` containing `holdings.json` (see `holdings.example.json`).
2. Create a **fine-grained personal access token**: *Only select repositories →* `market-dashboard-private`, *Repository permissions → Contents: Read-only*.
3. In this repo, go to **Settings → Secrets and variables → Actions** and add:
   - `PRIVATE_REPO_TOKEN`: the token
   - `HOLDINGS_PASSPHRASE`: a long passphrase (4+ random words)
4. Run the workflow, open the **Portfolio** tab and unlock it.

## Code structure

The code follows SOLID principles, so new data sources, signals, screens or tabs slot in without editing existing code.

```
dashboard/                    Python package: all logic, no entry points
  config.py                   config.json -> typed Settings
  analysis/                   pure functions, no I/O (easy to unit-test)
    indicators.py             SMA, RSI, MACD
    signals.py                SignalRule classes + DEFAULT_RULES registry
    screens.py                Screen objects + DEFAULT_SCREENS registry
    metrics.py, themes.py     per-symbol metrics, theme aggregation
  providers/                  adapters to the outside world
    base.py                   Protocols: PriceProvider, FundamentalsProvider, NewsProvider, Summarizer
    yahoo.py, google_news.py, gemini.py
  news.py, storage.py         news aggregation; the only module that knows docs/data paths
  pipeline.py                 MarketPipeline – orchestrates injected providers
  portfolio/                  crypto.py (Cipher), valuation.py (pure maths), service.py
scripts/                      composition roots: pick concrete classes, wire, run
tests/                        pytest suite using fakes for every provider
docs/                         static site (GitHub Pages)
  js/main.js                  composition root: services + tabs + global events
  js/core/ data/ ui/          formatting, theme, data access, Web Crypto, charts, detail sheet
  js/views/                   one class per tab, all extending View; registry in views/index.js
```

| Principle | Where you can see it |
|---|---|
| **Single responsibility** | Indicators, signal rules, screens, storage, providers and each UI tab are separate modules |
| **Open/closed** | Add a signal (a `SignalRule` class), a screen (a `Screen` entry), a tab (a `View` subclass) or a data source (a provider class) without changing existing code |
| **Liskov substitution** | Any `PriceProvider`/`Summarizer`/`Cipher` works in the pipeline; the tests swap in fakes |
| **Interface segregation** | Small Protocols (price history, fundamentals, news search, per-symbol news) instead of one big "data source" |
| **Dependency inversion** | `MarketPipeline` and `PortfolioService` depend on Protocols; only `scripts/*.py` and `js/main.js` choose concrete classes |

### Extending it

- **New signal:** add a class with `evaluate(ctx) -> list[Signal]` in `analysis/signals.py`, then append it to `DEFAULT_RULES`.
- **New screen:** append a `Screen(id, name, why, predicate)` to `DEFAULT_SCREENS`.
- **New data source** (e.g. Alpha Vantage, Bursa API): implement `PriceProvider.history()` and pass it in `scripts/fetch_data.py`.
- **New tab:** create `docs/js/views/<name>.js` extending `View`, then add it to `views/index.js`.
- **Tests:** `pip install -r scripts/requirements-dev.txt && python -m pytest`. CI runs them on every push. `tests/test_pipeline.py::test_pipeline_output_contract` pins the JSON keys the front end relies on.

## Customise

- **Watchlist / indices / news topics:** edit `config.json` (Yahoo symbols; Bursa stocks end in `.KL`). Pushing the change reruns the job.
- **Schedule:** edit the cron lines in `.github/workflows/update-data.yml` (times are in UTC).

## Tech

Python 3.12 (pandas, yfinance, feedparser, cryptography, pytest) · GitHub Actions · GitHub Pages · vanilla JS ES modules (no build step) · Web Crypto API · CSP · lightweight-charts · responsive, dark mode, installable as a PWA.

> Data comes from Yahoo Finance (unofficial, delayed) and Google News RSS. This is a learning project and not financial advice.
