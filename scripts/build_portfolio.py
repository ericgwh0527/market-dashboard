"""
Builds the ENCRYPTED portfolio file for the public dashboard.

Security model
--------------
* Your real holdings live in a PRIVATE repo (holdings.json). The workflow checks it
  out with a read-only token; it is never committed to this public repo.
* This script values the holdings with fresh prices (fetched in memory only – no
  per-holding files are written, so the public repo never reveals what you own),
  then encrypts the result with AES-256-GCM. The key is derived from the
  HOLDINGS_PASSPHRASE secret with PBKDF2-SHA256 (600k iterations).
* Only docs/data/portfolio.enc.json is published. The dashboard asks for the
  passphrase and decrypts it inside your browser (Web Crypto API).

Env:
  HOLDINGS_FILE        path to holdings.json (from the private repo checkout)
  HOLDINGS_PASSPHRASE  passphrase (GitHub secret)
If either is missing the script exits quietly and the portfolio tab stays locked/empty.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "portfolio.enc.json"
MYT = timezone(timedelta(hours=8))
ITER = 600_000

sys.path.insert(0, str(Path(__file__).parent))
from fetch_data import clean  # noqa: E402


# ------------------------------------------------------------- crypto (Web Crypto compatible)
def _key(passphrase: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(passphrase.encode())


def encrypt(obj, passphrase: str, salt: bytes | None = None) -> dict:
    """Fresh random IV every time. The salt is reused while the passphrase stays the
    same, so a browser that saved its (non-extractable) derived key stays unlocked."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt, iv = salt or os.urandom(16), os.urandom(12)
    ct = AESGCM(_key(passphrase, salt)).encrypt(iv, json.dumps(clean(obj), separators=(",", ":")).encode(), None)
    b = lambda x: base64.b64encode(x).decode()
    return {"v": 1, "alg": "AES-256-GCM", "kdf": "PBKDF2-SHA256", "iter": ITER, "salt": b(salt), "iv": b(iv), "ct": b(ct)}


def decrypt(blob: dict, passphrase: str):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    d = lambda x: base64.b64decode(x)
    pt = AESGCM(_key(passphrase, d(blob["salt"]))).decrypt(d(blob["iv"]), d(blob["ct"]), None)
    return json.loads(pt)


# ------------------------------------------------------------- valuation
def fetch_quotes(symbols: list[str]) -> dict[str, dict]:
    import yfinance as yf
    out = {}
    if not symbols:
        return out
    # Actions logs of a public repo are public: swallow all yfinance output so a
    # failed download can't print the names of the stocks you hold.
    import contextlib, io, logging
    logging.getLogger("yfinance").disabled = True
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        raw = yf.download(symbols, period="10d", interval="1d", group_by="ticker",
                          auto_adjust=False, threads=True, progress=False)
    for s in symbols:
        try:
            df = raw[s] if isinstance(raw.columns, pd.MultiIndex) else raw
            c = df["Close"].dropna()
            if len(c):
                out[s] = {"price": float(c.iloc[-1]), "prev": float(c.iloc[-2]) if len(c) > 1 else None,
                          "date": pd.Timestamp(c.index[-1]).strftime("%Y-%m-%d")}
        except Exception:
            pass
    return out


def guess_currency(symbol: str) -> str:
    return "MYR" if symbol.upper().endswith(".KL") else "USD"


def value_portfolio(h: dict) -> dict:
    base = h.get("base_currency", "MYR").upper()
    positions = [p for p in h.get("positions", []) if float(p.get("shares", 0) or 0) != 0]
    syms = sorted({p["symbol"] for p in positions})
    quotes = fetch_quotes(syms + ["MYR=X"])
    usdmyr = (quotes.get("MYR=X") or {}).get("price")
    if not usdmyr:
        latest = json.loads((ROOT / "docs/data/latest.json").read_text())
        usdmyr = next((i["price"] for i in latest.get("indices", []) if i["symbol"] == "MYR=X"), None)

    def to_base(amount, cur):
        if amount is None:
            return None
        cur = cur.upper()
        if cur == base:
            return amount
        if cur == "USD" and base == "MYR":
            return amount * usdmyr
        if cur == "MYR" and base == "USD":
            return amount / usdmyr
        return amount  # unknown pair – shown unconverted

    rows, tot_val, tot_cost, day_pl = [], 0.0, 0.0, 0.0
    for p in positions:
        s, sh = p["symbol"], float(p["shares"])
        cur = (p.get("currency") or guess_currency(s)).upper()
        q = quotes.get(s, {})
        price = q.get("price") or p.get("last_price")
        cost = float(p.get("avg_cost", 0) or 0)
        val = price * sh if price else None
        pl = (price - cost) * sh if price and cost else None
        dchg = (price / q["prev"] - 1) * 100 if q.get("prev") and price else None
        dpl = (price - q["prev"]) * sh if q.get("prev") and price else None
        vb, cb = to_base(val, cur), to_base(cost * sh, cur)
        tot_val += vb or 0
        tot_cost += cb or 0
        day_pl += to_base(dpl, cur) or 0
        rows.append({
            "symbol": s, "name": p.get("name") or s, "market": "MY" if s.upper().endswith(".KL") else "US",
            "currency": cur, "shares": sh, "avg_cost": cost, "price": price, "price_date": q.get("date"),
            "value": val, "value_base": vb, "cost_base": cb, "pl": pl, "pl_base": to_base(pl, cur),
            "pl_pct": (price / cost - 1) * 100 if price and cost else None,
            "day_chg_pct": dchg, "day_pl_base": to_base(dpl, cur), "note": p.get("note"),
            "stale_price": s not in quotes,
        })

    cash_rows = []
    for c in h.get("cash", []):
        amt, cur = float(c.get("amount", 0) or 0), c.get("currency", base).upper()
        cash_rows.append({"currency": cur, "amount": amt, "amount_base": to_base(amt, cur)})
    cash_base = sum(c["amount_base"] or 0 for c in cash_rows)

    total = tot_val + cash_base
    for r in rows:
        r["weight"] = (r["value_base"] / total * 100) if total and r["value_base"] else None
    rows.sort(key=lambda r: -(r["value_base"] or 0))

    alloc = {}
    for r in rows:
        alloc[r["market"]] = alloc.get(r["market"], 0) + (r["value_base"] or 0)
    if cash_base:
        alloc["Cash"] = cash_base

    now = datetime.now(timezone.utc)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "generated_at_myt": now.astimezone(MYT).strftime("%a %d %b %Y, %I:%M %p MYT"),
        "base_currency": base, "usdmyr": usdmyr, "holdings_updated": h.get("updated"),
        "totals": {
            "value": total, "invested_value": tot_val, "cash": cash_base, "cost": tot_cost,
            "pl": tot_val - tot_cost, "pl_pct": (tot_val / tot_cost - 1) * 100 if tot_cost else None,
            "day_pl": day_pl, "day_pl_pct": day_pl / (tot_val - day_pl) * 100 if tot_val - day_pl else None,
        },
        "positions": rows, "cash": cash_rows,
        "allocation": [{"name": k, "value": v, "pct": v / total * 100 if total else None} for k, v in alloc.items()],
    }


def main():
    path, pw = os.environ.get("HOLDINGS_FILE"), os.environ.get("HOLDINGS_PASSPHRASE")
    if not path or not pw or not Path(path).exists():
        print("Portfolio: no holdings file or passphrase configured – skipping.")
        return
    holdings = json.loads(Path(path).read_text(encoding="utf-8"))
    result = value_portfolio(holdings)

    # carry forward value history from the previous encrypted file
    history, salt = [], None
    if OUT.exists():
        try:
            prev_blob = json.loads(OUT.read_text())
            history = decrypt(prev_blob, pw).get("history", [])
            salt = base64.b64decode(prev_blob["salt"])
        except Exception:
            print("Portfolio: previous file could not be decrypted (passphrase changed?) – starting new history.")
    today = datetime.now(MYT).strftime("%Y-%m-%d")
    t = result["totals"]
    history = [x for x in history if x.get("date") != today]
    history.append({"date": today, "value": t["value"], "cost": t["cost"], "cash": t["cash"]})
    result["history"] = history[-1000:]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(encrypt(result, pw, salt)), encoding="utf-8")
    print(f"Portfolio encrypted -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
