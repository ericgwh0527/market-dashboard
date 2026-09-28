"""When is the (rate-limited) AI brief allowed to be regenerated?

The data job can run many times a day (schedule, midday run, manual "Update"
button, pushes). The AI brief only needs refreshing after each market close,
and must never be spammable, so the decision lives in one small policy object.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

MODES = ("auto", "force", "off")


class SummaryPolicy(Protocol):
    def decide(self, previous: dict | None, now: datetime) -> tuple[bool, str]:
        """Return (generate?, reason)."""


@dataclass(frozen=True)
class CooldownPolicy:
    """
    mode "auto"  – scheduled after-close runs: generate unless on cooldown
    mode "force" – manual run with the "AI brief" box ticked: same cooldown still applies
    mode "off"   – everything else (midday, pushes, plain manual runs): reuse the last brief
    """
    mode: str = "auto"
    cooldown: timedelta = timedelta(hours=1)

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")

    def decide(self, previous: dict | None, now: datetime) -> tuple[bool, str]:
        if self.mode == "off":
            return False, "AI brief not requested for this run"
        last = _parse(previous.get("generated_at")) if previous else None
        if last and now - last < self.cooldown:
            mins = int((self.cooldown - (now - last)).total_seconds() // 60) + 1
            return False, f"AI brief on cooldown ({mins} min left)"
        return True, "generating AI brief"


def _parse(iso: str | None) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(iso))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
