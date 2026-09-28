"""Typed view of config.json."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    market: str | None = None   # "MY" / "US" for stocks; None for indices & macro
    theme: str | None = None
    group: str | None = None    # display group for indices

    @property
    def is_stock(self) -> bool:
        return self.market is not None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass(frozen=True)
class NewsQuery:
    label: str
    query: str


@dataclass(frozen=True)
class Settings:
    indices: list[Instrument]
    stocks: list[Instrument]
    news_queries: list[NewsQuery] = field(default_factory=list)
    gemini_model: str = "gemini-2.5-flash"

    @property
    def all_instruments(self) -> list[Instrument]:
        return self.indices + self.stocks


def load_settings(path: Path) -> Settings:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return Settings(
        indices=[Instrument(i["symbol"], i["name"], group=i.get("group")) for i in raw["indices"]],
        stocks=[Instrument(s["symbol"], s["name"], market=s["market"], theme=s.get("theme")) for s in raw["stocks"]],
        news_queries=[NewsQuery(q["label"], q["query"]) for q in raw.get("news_queries", [])],
        gemini_model=raw.get("gemini_model", "gemini-2.5-flash"),
    )
