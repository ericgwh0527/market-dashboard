"""
Market dashboard data builder.

Pulls prices (Yahoo Finance via yfinance), computes indicators and signals,
collects news (Yahoo + Google News RSS), optionally asks Gemini for a short
daily summary, and writes JSON files the dashboard (docs/) reads.

Outputs (all under docs/data/):
  latest.json                 everything the dashboard's main view needs
  series/<SYMBOL>.json        ~1 year of daily OHLCV + indicator lines per symbol
  history/<YYYY-MM-DD>_<session>.json   compact daily snapshot (for trend questions)
  summaries/<YYYY-MM-DD>_<session>.md   the AI summary text, if generated

Run locally:  python scripts/fetch_data.py
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
MYT = timezone(timedelta(hours=8))


# ----------------------------------------------------------------- helpers
def clean(v):
    """Make values JSON-safe (NaN/inf -> None, numpy -> python, round floats)."""
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (np.floating, float)):
        v = float(v)
        if math.isnan(v) or math.isinf(v):
            return None
        return round(v, 4)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    return v


def pct(a, b):
    try:
        if a is None or b is None or b == 0 or pd.isna(a) or pd.isna(b):
            return None
        return (a / b - 1) * 100
    except Exception:
        return None


def safe_name(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", symbol)


def write_json(path: Path, obj, compact=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(clean(obj), f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(clean(obj), f, ensure_ascii=False, indent=1)


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


# ----------------------------------------------------------------- indicators
def rsi(close: pd.Series, n=14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(dn != 0, 100.0)


def macd(close: pd.Series):
    e12 = close.ewm(span=12, adjust=False).mean()
    e26 = close.ewm(span=26, adjust=False).mean()
    line = e12 - e26
    sig = line.ewm(span=9, adjust=False).mean()
    return line, sig, line - sig


def analyse(df: pd.DataFrame) -> dict:
    """df: daily OHLCV indexed by date (ascending), NaN rows removed."""
    c, v = df["Close"], df["Volume"]
    last = c.iloc[-1]
    s20, s50, s200 = c.rolling(20).mean(), c.rolling(50).mean(), c.rolling(200).mean()
    r = rsi(c)
    m_line, m_sig, m_hist = macd(c)
    y1 = c.iloc[-252:]
    hi52, lo52 = df["High"].iloc[-252:].max(), df["Low"].iloc[-252:].min()

    def ret(days):
        return pct(last, c.iloc[-days - 1]) if len(c) > days else None

    this_year = c[c.index.year == c.index[-1].year]
    prev_year_close = c[c.index.year < c.index[-1].year]
    ytd = pct(last, prev_year_close.iloc[-1]) if len(prev_year_close) else pct(last, this_year.iloc[0])

    vol20 = v.iloc[-21:-1].mean() if len(v) > 21 else None
    vol_ratio = (v.iloc[-1] / vol20) if vol20 and vol20 > 0 else None
    daily = c.pct_change().dropna()
    volatility = daily.iloc[-60:].std() * math.sqrt(252) * 100 if len(daily) > 20 else None

    L = lambda s: s.iloc[-1] if len(s) and not pd.isna(s.iloc[-1]) else None
    sma20, sma50, sma200, rsi14 = L(s20), L(s50), L(s200), L(r)

    # Trend label
    if sma50 and sma200:
        if last > sma50 > sma200:
            trend = "Uptrend"
        elif last < sma50 < sma200:
            trend = "Downtrend"
        else:
            trend = "Mixed"
    elif sma50:
        trend = "Uptrend" if last > sma50 else "Downtrend"
    else:
        trend = "n/a"

    # Signals (plain-English, each with a type for colouring)
    sig = []
    if rsi14 is not None:
        if rsi14 >= 70:
            sig.append(("warn", f"RSI {rsi14:.0f} – overbought (ran up fast)"))
        elif rsi14 <= 30:
            sig.append(("info", f"RSI {rsi14:.0f} – oversold (sold off hard)"))
    if len(s200.dropna()) > 10:
        cross = (s50 - s200).iloc[-10:]
        if (cross.iloc[0] < 0) and (cross.iloc[-1] > 0):
            sig.append(("good", "Golden cross – 50-day avg crossed above 200-day"))
        if (cross.iloc[0] > 0) and (cross.iloc[-1] < 0):
            sig.append(("bad", "Death cross – 50-day avg crossed below 200-day"))
    if len(m_hist) > 3:
        if m_hist.iloc[-1] > 0 and m_hist.iloc[-3] <= 0:
            sig.append(("good", "MACD turned bullish (momentum improving)"))
        if m_hist.iloc[-1] < 0 and m_hist.iloc[-3] >= 0:
            sig.append(("bad", "MACD turned bearish (momentum fading)"))
    if hi52 and last >= hi52 * 0.99:
        sig.append(("good", "At / near 52-week high"))
    if lo52 and last <= lo52 * 1.01:
        sig.append(("bad", "At / near 52-week low"))
    if vol_ratio and vol_ratio >= 2:
        sig.append(("info", f"Volume {vol_ratio:.1f}× the 20-day average"))
    if sma200 and len(c) > 2:
        prev = c.iloc[-2]
        p200 = s200.iloc[-2]
        if prev < p200 <= last or (prev < p200 and last > sma200):
            sig.append(("good", "Closed back above 200-day average"))
        elif prev > p200 and last < sma200:
            sig.append(("bad", "Fell below 200-day average"))

    return {
        "price": last,
        "prev_close": c.iloc[-2] if len(c) > 1 else None,
        "date": c.index[-1].strftime("%Y-%m-%d"),
        "chg_1d": ret(1), "chg_5d": ret(5), "chg_1m": ret(21), "chg_3m": ret(63),
        "chg_6m": ret(126), "chg_1y": ret(252), "chg_ytd": ytd,
        "hi_52w": hi52, "lo_52w": lo52,
        "from_hi_52w": pct(last, hi52),
        "sma20": sma20, "sma50": sma50, "sma200": sma200,
        "above_sma50": (last > sma50) if sma50 else None,
        "above_sma200": (last > sma200) if sma200 else None,
        "rsi14": rsi14,
        "macd_hist": L(m_hist),
        "volume": v.iloc[-1], "vol_ratio": vol_ratio,
        "volatility_60d": volatility,
        "trend": trend,
        "signals": [{"type": t, "text": x} for t, x in sig],
        "spark": [round(float(x), 4) for x in c.iloc[-66:].tolist()],
    }, pd.DataFrame({"sma20": s20, "sma50": s50, "sma200": s200, "rsi": r, "macd_hist": m_hist})


# ----------------------------------------------------------------- prices
def download_prices(symbols: list[str]) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    out: dict[str, pd.DataFrame] = {}
    for attempt in range(3):
        todo = [s for s in symbols if s not in out]
        if not todo:
            break
        try:
            raw = yf.download(todo, period="2y", interval="1d", group_by="ticker",
                              auto_adjust=False, threads=True, progress=False)
        except Exception as e:
            print(f"download attempt {attempt+1} failed: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
            continue
        for s in todo:
            try:
                df = raw[s] if isinstance(raw.columns, pd.MultiIndex) else raw
                df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
                df["Volume"] = df["Volume"].fillna(0)
                if len(df) >= 30:
                    df.index = pd.to_datetime(df.index).tz_localize(None)
                    out[s] = df.sort_index()
            except Exception:
                pass
        if len(out) < len(symbols):
            time.sleep(3)
    missing = [s for s in symbols if s not in out]
    if missing:
        print("No price data for:", ", ".join(missing), file=sys.stderr)
    return out


def fetch_fundamentals(symbols: list[str], previous: dict) -> dict:
    """Valuation facts from yfinance .info (slow, sometimes rate-limited).
    Falls back to the previous run's values per symbol."""
    import yfinance as yf

    keys = {
        "longName": "long_name", "sector": "sector", "industry": "industry",
        "currency": "currency", "marketCap": "market_cap",
        "trailingPE": "pe", "forwardPE": "forward_pe", "priceToBook": "pb",
        "dividendYield": "div_yield", "trailingEps": "eps",
        "profitMargins": "profit_margin", "revenueGrowth": "revenue_growth",
        "earningsGrowth": "earnings_growth", "returnOnEquity": "roe",
        "debtToEquity": "debt_to_equity", "beta": "beta",
        "targetMeanPrice": "target_price", "recommendationKey": "analyst_view",
        "numberOfAnalystOpinions": "analyst_count",
    }
    res = {}
    for s in symbols:
        info = None
        for attempt in range(2):
            try:
                info = yf.Ticker(s).info or {}
                break
            except Exception as e:
                print(f"info {s} failed: {e}", file=sys.stderr)
                time.sleep(2)
        if info:
            f = {v: info.get(k) for k, v in keys.items()}
            # yfinance has changed dividendYield units across versions (0.05 vs 5.0)
            dy = f.get("div_yield")
            if isinstance(dy, (int, float)) and dy is not None and dy < 1:
                f["div_yield"] = dy * 100
            for k in ("profit_margin", "revenue_growth", "earnings_growth", "roe"):
                if isinstance(f.get(k), (int, float)):
                    f[k] = f[k] * 100
            try:
                ts = info.get("earningsTimestamp") or info.get("earningsTimestampStart")
                if ts:
                    f["next_earnings"] = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            except Exception:
                pass
            res[s] = f
        elif s in previous:
            res[s] = previous[s]
        time.sleep(0.4)
    return res


# ----------------------------------------------------------------- news
def _yahoo_item(n: dict) -> dict | None:
    c = n.get("content") if isinstance(n.get("content"), dict) else n
    title = c.get("title")
    url = ((c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url")
           or c.get("link"))
    pub = c.get("pubDate") or c.get("displayTime")
    if not pub and c.get("providerPublishTime"):
        pub = datetime.fromtimestamp(c["providerPublishTime"], tz=timezone.utc).isoformat()
    src = (c.get("provider") or {}).get("displayName") or c.get("publisher") or "Yahoo Finance"
    if not title or not url:
        return None
    return {"title": title, "url": url, "published": pub, "source": src}


def yahoo_news(symbol: str, limit=6) -> list[dict]:
    import yfinance as yf
    try:
        items = yf.Ticker(symbol).news or []
    except Exception:
        return []
    out = [x for x in (_yahoo_item(n) for n in items) if x]
    return out[:limit]


def google_news(query: str, limit=8, when="3d") -> list[dict]:
    import feedparser
    q = urllib.parse.quote(f"{query} when:{when}")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-MY&gl=MY&ceid=MY:en"
    try:
        feed = feedparser.parse(url, agent="Mozilla/5.0 (market-dashboard)")
    except Exception:
        return []
    out = []
    for e in feed.entries[:limit]:
        title = e.get("title", "")
        src = (e.get("source") or {}).get("title") if isinstance(e.get("source"), dict) else None
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3]
        pub = None
        if e.get("published_parsed"):
            pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).isoformat()
        out.append({"title": title, "url": e.get("link"), "published": pub, "source": src or "Google News"})
    return out


def dedupe(items: list[dict]) -> list[dict]:
    seen, out = set(), []
    for it in items:
        k = re.sub(r"\W+", "", (it.get("title") or "").lower())[:70]
        if k and k not in seen:
            seen.add(k)
            out.append(it)
    return out


def sort_news(items):
    def key(it):
        try:
            return pd.Timestamp(it.get("published")).tz_convert("UTC").value if pd.Timestamp(it.get("published")).tzinfo else pd.Timestamp(it.get("published")).tz_localize("UTC").value
        except Exception:
            return 0
    return sorted(items, key=key, reverse=True)


# ----------------------------------------------------------------- AI summary
def gemini_summary(payload: dict, model: str) -> str | None:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    import requests

    prompt = (
        "You write a short daily market brief for a university student in Malaysia who is "
        "learning about investing. Use ONLY the data below (do not invent numbers or news). "
        "Plain English, no hype, no buy/sell recommendations.\n\n"
        "Format in Markdown, max ~220 words:\n"
        "**Big picture** – 2 sentences on Malaysia (KLCI, ringgit) and US markets.\n"
        "**Movers** – 3 bullets on notable watchlist moves and the likely reason if a headline supports it.\n"
        "**Worth watching** – 2 bullets from the technical signals.\n"
        "**Concept of the day** – explain ONE term that appears in today's data (e.g. RSI, 200-day average, VIX) in 2 sentences.\n\n"
        f"DATA (JSON):\n{json.dumps(clean(payload), ensure_ascii=False)[:24000]}"
    )
    models = [model, "gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash"]
    for m in dict.fromkeys(models):
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                params={"key": key},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1200}},
                timeout=90,
            )
            if r.status_code != 200:
                print(f"Gemini {m}: HTTP {r.status_code} {r.text[:200]}", file=sys.stderr)
                continue
            parts = r.json()["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
            if text:
                return text
        except Exception as e:
            print(f"Gemini {m} failed: {e}", file=sys.stderr)
    return None


# ----------------------------------------------------------------- main
def main():
    cfg = load_json(ROOT / "config.json")
    prev = load_json(DATA / "latest.json", {}) or {}
    prev_fund = {s["symbol"]: s.get("fundamentals") for s in prev.get("stocks", []) if s.get("fundamentals")}

    now = datetime.now(timezone.utc)
    now_myt = now.astimezone(MYT)
    session = os.environ.get("SESSION") or ("after-bursa" if 8 <= now.hour < 18 else "after-us")

    idx_cfg, stk_cfg = cfg["indices"], cfg["stocks"]
    all_syms = [x["symbol"] for x in idx_cfg + stk_cfg]
    print(f"Downloading prices for {len(all_syms)} symbols …")
    prices = download_prices(all_syms)
    if len(prices) < len(all_syms) * 0.5:
        print("Too few symbols downloaded – keeping previous data.", file=sys.stderr)
        sys.exit(1)

    def build(item, with_fund=False, fund=None):
        s = item["symbol"]
        df = prices.get(s)
        if df is None:
            # keep last known entry so the dashboard doesn't lose rows
            old = next((x for x in prev.get("stocks", []) + prev.get("indices", []) if x["symbol"] == s), None)
            if old:
                old = dict(old); old["stale"] = True
            return old
        m, ind = analyse(df)
        # series file (last ~1y) for the chart
        tail = df.iloc[-260:]
        it = ind.loc[tail.index]
        write_json(DATA / "series" / f"{safe_name(s)}.json", {
            "symbol": s,
            "d": [d.strftime("%Y-%m-%d") for d in tail.index],
            "o": tail["Open"].round(4).tolist(), "h": tail["High"].round(4).tolist(),
            "l": tail["Low"].round(4).tolist(), "c": tail["Close"].round(4).tolist(),
            "v": tail["Volume"].astype(float).tolist(),
            "sma20": it["sma20"].round(4).tolist(), "sma50": it["sma50"].round(4).tolist(),
            "sma200": it["sma200"].round(4).tolist(), "rsi": it["rsi"].round(2).tolist(),
        })
        out = {**item, **m, "file": f"series/{safe_name(s)}.json"}
        if with_fund:
            out["fundamentals"] = (fund or {}).get(s)
        return out

    indices = [x for x in (build(i) for i in idx_cfg) if x]

    print("Fetching fundamentals …")
    fund = fetch_fundamentals([s["symbol"] for s in stk_cfg], prev_fund)
    stocks = [x for x in (build(s, True, fund) for s in stk_cfg) if x]

    # per-stock news
    print("Fetching news …")
    for s in stocks:
        items = yahoo_news(s["symbol"], 5)
        if s["market"] == "MY" or len(items) < 3:
            items += google_news(f'"{s["name"]}" Bursa' if s["market"] == "MY" else f'{s["name"]} stock', 5, "7d")
        s["news"] = sort_news(dedupe(items))[:6]
        time.sleep(0.3)

    market_news = []
    for q in cfg.get("news_queries", []):
        for it in google_news(q["query"], 8, "2d"):
            it["topic"] = q["label"]
            market_news.append(it)
    market_news = sort_news(dedupe(market_news))[:40]

    # themes / sector heat
    themes = {}
    for s in stocks:
        t = themes.setdefault(f'{s["market"]} · {s["theme"]}', {"name": s["theme"], "market": s["market"], "chg_1d": [], "chg_1m": [], "members": []})
        t["chg_1d"].append(s.get("chg_1d")); t["chg_1m"].append(s.get("chg_1m")); t["members"].append(s["symbol"])
    theme_list = []
    for k, t in themes.items():
        a = [x for x in t["chg_1d"] if x is not None]; b = [x for x in t["chg_1m"] if x is not None]
        theme_list.append({"key": k, "name": t["name"], "market": t["market"], "members": t["members"],
                           "chg_1d": float(np.mean(a)) if a else None, "chg_1m": float(np.mean(b)) if b else None})

    # screener buckets
    def pick(cond):
        return [s["symbol"] for s in stocks if cond(s)]
    screens = [
        {"id": "uptrend", "name": "Healthy uptrend", "why": "Price above 50-day and 200-day averages – the trend is up.",
         "symbols": pick(lambda s: s.get("trend") == "Uptrend")},
        {"id": "near_high", "name": "Near 52-week high", "why": "Within 3% of the highest price of the past year – strong momentum.",
         "symbols": pick(lambda s: s.get("from_hi_52w") is not None and s["from_hi_52w"] > -3)},
        {"id": "oversold", "name": "Oversold (RSI < 35)", "why": "Sold off quickly; sometimes bounces, sometimes keeps falling.",
         "symbols": pick(lambda s: s.get("rsi14") is not None and s["rsi14"] < 35)},
        {"id": "overbought", "name": "Overbought (RSI > 70)", "why": "Ran up fast; risk of a pullback or pause.",
         "symbols": pick(lambda s: s.get("rsi14") is not None and s["rsi14"] > 70)},
        {"id": "vol_spike", "name": "Unusual volume", "why": "Traded ≥1.8× normal volume – something is happening.",
         "symbols": pick(lambda s: (s.get("vol_ratio") or 0) >= 1.8)},
        {"id": "value", "name": "Lower P/E + dividend", "why": "P/E under 15 and dividend yield over 3% – classic 'value' filter.",
         "symbols": pick(lambda s: (s.get("fundamentals") or {}).get("pe") and 0 < s["fundamentals"]["pe"] < 15
                          and ((s["fundamentals"].get("div_yield") or 0) > 3))},
        {"id": "downtrend", "name": "Downtrend", "why": "Below 50-day and 200-day averages – the trend is down.",
         "symbols": pick(lambda s: s.get("trend") == "Downtrend")},
    ]

    latest = {
        "generated_at": now.isoformat(timespec="seconds"),
        "generated_at_myt": now_myt.strftime("%a %d %b %Y, %I:%M %p MYT"),
        "session": session,
        "indices": indices,
        "stocks": stocks,
        "themes": sorted(theme_list, key=lambda t: (t["market"], -(t["chg_1d"] or 0))),
        "screens": screens,
        "market_news": market_news,
        "summary": None,
    }

    # AI summary (optional)
    brief = {
        "indices": [{k: i.get(k) for k in ("name", "price", "chg_1d", "chg_5d", "chg_1m", "trend")} for i in indices],
        "stocks": [{k: s.get(k) for k in ("name", "symbol", "market", "price", "chg_1d", "chg_5d", "chg_1m", "rsi14", "trend")}
                   | {"signals": [x["text"] for x in s.get("signals", [])],
                      "headlines": [n["title"] for n in s.get("news", [])[:2]]} for s in stocks],
        "market_headlines": [n["title"] for n in market_news[:15]],
    }
    text = gemini_summary(brief, cfg.get("gemini_model", "gemini-2.5-flash"))
    if text:
        latest["summary"] = {"text": text, "model": "Gemini", "generated_at_myt": latest["generated_at_myt"]}
        p = DATA / "summaries" / f"{now_myt:%Y-%m-%d}_{session}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# Market brief – {latest['generated_at_myt']}\n\n{text}\n", encoding="utf-8")
    elif prev.get("summary"):
        latest["summary"] = {**prev["summary"], "stale": True}

    write_json(DATA / "latest.json", latest)

    # compact history snapshot (one per session per day)
    snap = {
        "generated_at": latest["generated_at"], "session": session,
        "rows": [{k: x.get(k) for k in ("symbol", "name", "price", "chg_1d", "chg_1m", "rsi14", "trend", "vol_ratio", "from_hi_52w")}
                 | {"signals": [s["text"] for s in x.get("signals", [])]} for x in indices + stocks],
        "top_headlines": [n["title"] for n in market_news[:10]],
    }
    write_json(DATA / "history" / f"{now_myt:%Y-%m-%d}_{session}.json", snap, compact=False)

    # index of history files so the dashboard / Claude can list them
    hist = sorted(p.name for p in (DATA / "history").glob("*.json") if p.name != "index.json")
    write_json(DATA / "history" / "index.json", {"files": hist})

    print(f"Done: {len(indices)} indices, {len(stocks)} stocks, {len(market_news)} headlines, "
          f"summary={'yes' if text else 'no'}")


if __name__ == "__main__":
    main()
