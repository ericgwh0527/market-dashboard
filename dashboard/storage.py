"""Where every output file lives. The only module that knows the docs/data layout."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .jsonio import read_json, write_json


def safe_name(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", symbol)


class DataStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    # paths
    @property
    def latest_path(self) -> Path:
        return self.root / "latest.json"

    @property
    def portfolio_path(self) -> Path:
        return self.root / "portfolio.enc.json"

    def series_rel(self, symbol: str) -> str:
        return f"series/{safe_name(symbol)}.json"

    # reads
    def previous_latest(self) -> dict:
        return read_json(self.latest_path, {}) or {}

    def previous_portfolio(self) -> dict | None:
        return read_json(self.portfolio_path)

    # writes
    def save_latest(self, data: dict) -> None:
        write_json(self.latest_path, data)

    def save_series(self, symbol: str, series: dict) -> str:
        rel = self.series_rel(symbol)
        write_json(self.root / rel, {"symbol": symbol, **series})
        return rel

    def save_history(self, when: datetime, session: str, snapshot: dict) -> None:
        write_json(self.root / "history" / f"{when:%Y-%m-%d}_{session}.json", snapshot, compact=False)
        files = sorted(p.name for p in (self.root / "history").glob("*.json") if p.name != "index.json")
        write_json(self.root / "history" / "index.json", {"files": files})

    def save_summary(self, when: datetime, session: str, title: str, text: str) -> None:
        p = self.root / "summaries" / f"{when:%Y-%m-%d}_{session}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# Market brief – {title}\n\n{text}\n", encoding="utf-8")

    def save_portfolio(self, blob: dict) -> None:
        write_json(self.portfolio_path, blob, compact=False)
