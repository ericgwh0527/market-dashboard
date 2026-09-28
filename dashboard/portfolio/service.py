"""PortfolioService: holdings -> quotes -> valuation -> encrypted file.

Imports nothing heavier than the stdlib and `cryptography`, because this code
runs in the job that knows the passphrase."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..jsonio import clean
from ..storage import DataStore
from .crypto import Cipher
from .quotes import QuoteProvider
from .valuation import append_history, value_portfolio

MYT = timezone(timedelta(hours=8))


class NoQuotes(RuntimeError):
    """Price source down: better to keep yesterday's file than publish zeros."""
FX_SYMBOL = "MYR=X"


@dataclass
class PortfolioService:
    quotes: QuoteProvider      # must be silent: Actions logs are public
    cipher: Cipher
    store: DataStore

    def run(self, holdings: dict, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        symbols = sorted({p["symbol"] for p in holdings.get("positions", [])})
        quotes = self.quotes.quotes(symbols + [FX_SYMBOL])
        if symbols and not any(s in quotes for s in symbols):
            raise NoQuotes("no prices for any holding – keeping the previous file")
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

    def _fallback_usdmyr(self) -> float | None:
        latest = self.store.previous_latest()
        return next((i["price"] for i in latest.get("indices", []) if i["symbol"] == FX_SYMBOL), None)
