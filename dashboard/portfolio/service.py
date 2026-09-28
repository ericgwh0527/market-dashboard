"""PortfolioService: holdings file -> quotes -> valuation -> encrypted file."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..jsonio import clean
from ..providers.base import PriceProvider
from ..storage import DataStore
from .crypto import Cipher
from .valuation import Quote, append_history, value_portfolio

MYT = timezone(timedelta(hours=8))
FX_SYMBOL = "MYR=X"


@dataclass
class PortfolioService:
    prices: PriceProvider      # should be a *quiet* provider: logs are public
    cipher: Cipher
    store: DataStore

    def run(self, holdings: dict, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        symbols = sorted({p["symbol"] for p in holdings.get("positions", [])})
        quotes = self._quotes(symbols + [FX_SYMBOL])
        usdmyr = quotes.pop(FX_SYMBOL).price if FX_SYMBOL in quotes else self._fallback_usdmyr()

        result = value_portfolio(holdings, quotes, usdmyr)
        result["generated_at"] = now.isoformat(timespec="seconds")
        result["generated_at_myt"] = now.astimezone(MYT).strftime("%a %d %b %Y, %I:%M %p MYT")

        previous = self.store.previous_portfolio()
        history = []
        if previous:
            try:
                history = self.cipher.decrypt(previous).get("history", [])
            except Exception:
                print("Portfolio: previous file could not be decrypted (passphrase changed?) – new history.")
        result["history"] = append_history(history, now.astimezone(MYT).strftime("%Y-%m-%d"), result["totals"])

        self.store.save_portfolio(self.cipher.encrypt(clean(result), previous))
        return result

    def _quotes(self, symbols: list[str]) -> dict[str, Quote]:
        frames = self.prices.history(symbols, period="1mo")
        out = {}
        for s, df in frames.items():
            c = df["Close"].dropna()
            if len(c):
                out[s] = Quote(float(c.iloc[-1]), float(c.iloc[-2]) if len(c) > 1 else None,
                               c.index[-1].strftime("%Y-%m-%d"))
        return out

    def _fallback_usdmyr(self) -> float | None:
        latest = self.store.previous_latest()
        return next((i["price"] for i in latest.get("indices", []) if i["symbol"] == FX_SYMBOL), None)
