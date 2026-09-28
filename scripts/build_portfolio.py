"""Entry point: value your private holdings and publish them ENCRYPTED.

Security model (details in README):
* holdings.json lives in a PRIVATE repo; the workflow checks it out read-only and
  deletes it before committing. It is never written to this public repo.
* Prices for your holdings are fetched with a *quiet* provider (no log output),
  and no per-holding files are written, so nothing public reveals what you own.
* Only docs/data/portfolio.enc.json (AES-256-GCM, PBKDF2 600k) is published.

Env: HOLDINGS_FILE, HOLDINGS_PASSPHRASE. If either is missing, it exits quietly.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.portfolio.crypto import AesGcmCipher  # noqa: E402
from dashboard.portfolio.service import PortfolioService  # noqa: E402
from dashboard.providers.yahoo import YahooPriceProvider  # noqa: E402
from dashboard.storage import DataStore  # noqa: E402


def main() -> int:
    path, pw = os.environ.get("HOLDINGS_FILE"), os.environ.get("HOLDINGS_PASSPHRASE")
    if not path or not pw or not Path(path).exists():
        print("Portfolio: no holdings file or passphrase configured – skipping.")
        return 0
    try:
        holdings = json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError:
        print("Portfolio: holdings.json is not valid JSON – skipping.")
        return 1
    service = PortfolioService(
        prices=YahooPriceProvider(quiet=True, min_rows=1),
        cipher=AesGcmCipher(pw),
        store=DataStore(ROOT / "docs" / "data"),
    )
    try:
        service.run(holdings)
    except Exception as e:
        # Actions logs are public: a traceback could quote holdings values, so print the type only.
        print(f"Portfolio step failed ({type(e).__name__}); previous encrypted file kept.")
        return 1
    print("Portfolio encrypted -> docs/data/portfolio.enc.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
