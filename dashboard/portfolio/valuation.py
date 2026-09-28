"""Pure portfolio maths: holdings + quotes + FX in, valued portfolio out."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Quote:
    price: float
    prev: float | None = None
    date: str | None = None


class FxConverter:
    """Converts between MYR and USD with one USD/MYR rate. Unknown pairs pass through unchanged."""
    def __init__(self, base: str, usdmyr: float | None):
        self.base, self.usdmyr = base.upper(), usdmyr

    def to_base(self, amount: float | None, cur: str) -> float | None:
        if amount is None:
            return None
        cur = cur.upper()
        if cur == self.base or not self.usdmyr:
            return amount
        if (cur, self.base) == ("USD", "MYR"):
            return amount * self.usdmyr
        if (cur, self.base) == ("MYR", "USD"):
            return amount / self.usdmyr
        return amount


def market_of(symbol: str) -> str:
    return "MY" if symbol.upper().endswith(".KL") else "US"


def default_currency(symbol: str) -> str:
    return "MYR" if market_of(symbol) == "MY" else "USD"


def shares_of(p: dict) -> float:
    return float(p.get("shares", p.get("qty", 0)) or 0)


def value_position(p: dict, q: Quote | None, fx: FxConverter) -> dict:
    s, sh = p["symbol"], shares_of(p)
    cur = (p.get("currency") or default_currency(s)).upper()
    price = q.price if q else p.get("last_price")
    cost = float(p.get("avg_cost", 0) or 0)
    prev = q.prev if q else None
    val = price * sh if price else None
    pl = (price - cost) * sh if price and cost else None
    dpl = (price - prev) * sh if price and prev else None
    return {
        "symbol": s, "name": p.get("name") or s, "market": market_of(s), "currency": cur,
        "shares": sh, "avg_cost": cost, "price": price, "price_date": q.date if q else None,
        "value": val, "value_base": fx.to_base(val, cur), "cost_base": fx.to_base(cost * sh, cur),
        "pl": pl, "pl_base": fx.to_base(pl, cur),
        "pl_pct": (price / cost - 1) * 100 if price and cost else None,
        "day_chg_pct": (price / prev - 1) * 100 if price and prev else None,
        "day_pl_base": fx.to_base(dpl, cur), "note": p.get("note"), "stale_price": q is None,
    }


def value_portfolio(holdings: dict, quotes: dict[str, Quote], usdmyr: float | None) -> dict:
    base = holdings.get("base_currency", "MYR").upper()
    fx = FxConverter(base, usdmyr)
    rows = [value_position(p, quotes.get(p["symbol"]), fx) for p in holdings.get("positions", []) if shares_of(p)]

    cash = []
    for c in holdings.get("cash", []):
        amt, cur = float(c.get("amount", 0) or 0), c.get("currency", base).upper()
        cash.append({"currency": cur, "amount": amt, "amount_base": fx.to_base(amt, cur)})
    cash_base = sum(c["amount_base"] or 0 for c in cash)

    invested = sum(r["value_base"] or 0 for r in rows)
    cost = sum(r["cost_base"] or 0 for r in rows)
    day_pl = sum(r["day_pl_base"] or 0 for r in rows)
    total = invested + cash_base
    for r in rows:
        r["weight"] = r["value_base"] / total * 100 if total and r["value_base"] else None
    rows.sort(key=lambda r: -(r["value_base"] or 0))

    alloc: dict[str, float] = {}
    for r in rows:
        alloc[r["market"]] = alloc.get(r["market"], 0) + (r["value_base"] or 0)
    if cash_base:
        alloc["Cash"] = cash_base

    return {
        "base_currency": base, "usdmyr": usdmyr, "holdings_updated": holdings.get("updated"),
        "totals": {
            "value": total, "invested_value": invested, "cash": cash_base, "cost": cost,
            "pl": invested - cost, "pl_pct": (invested / cost - 1) * 100 if cost else None,
            "day_pl": day_pl, "day_pl_pct": day_pl / (invested - day_pl) * 100 if invested - day_pl else None,
        },
        "positions": rows, "cash": cash,
        "allocation": [{"name": k, "value": v, "pct": v / total * 100 if total else None} for k, v in alloc.items()],
    }


def append_history(history: list[dict], date: str, totals: dict, keep: int = 1000) -> list[dict]:
    """One point per day; a later run on the same day replaces the earlier one."""
    out = [h for h in history if h.get("date") != date]
    out.append({"date": date, "value": totals["value"], "cost": totals["cost"], "cash": totals["cash"]})
    return sorted(out, key=lambda h: h["date"])[-keep:]
