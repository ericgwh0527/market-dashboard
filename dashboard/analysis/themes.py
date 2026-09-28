"""Group watchlist stocks by market + theme and average their moves."""
from __future__ import annotations

from statistics import mean


def aggregate_themes(rows: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    for r in rows:
        key = f'{r["market"]} · {r["theme"]}'
        g = groups.setdefault(key, {"key": key, "name": r["theme"], "market": r["market"], "members": [], "_1d": [], "_1m": []})
        g["members"].append(r["symbol"])
        if r.get("chg_1d") is not None:
            g["_1d"].append(r["chg_1d"])
        if r.get("chg_1m") is not None:
            g["_1m"].append(r["chg_1m"])
    out = []
    for g in groups.values():
        a, b = g.pop("_1d"), g.pop("_1m")
        out.append({**g, "chg_1d": mean(a) if a else None, "chg_1m": mean(b) if b else None})
    return sorted(out, key=lambda t: (t["market"], -(t["chg_1d"] or 0)))
