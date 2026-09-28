import json

import pytest

from dashboard.portfolio.crypto import AesGcmCipher
from dashboard.portfolio.service import PortfolioService
from dashboard.portfolio.valuation import FxConverter, Quote, append_history, value_portfolio
from dashboard.storage import DataStore

HOLDINGS = {
    "base_currency": "MYR",
    "positions": [
        {"symbol": "1023.KL", "shares": 100, "avg_cost": 8.0},
        {"symbol": "NVDA", "qty": 2, "avg_cost": 100.0},
        {"symbol": "ZERO.KL", "shares": 0, "avg_cost": 1},
    ],
    "cash": [{"currency": "MYR", "amount": 500}],
}


def test_valuation_converts_usd_and_weights_sum_to_invested_share():
    p = value_portfolio(HOLDINGS, {"1023.KL": Quote(9.0, 8.5), "NVDA": Quote(150.0, 140.0)}, usdmyr=4.0)
    t = p["totals"]
    assert t["invested_value"] == pytest.approx(900 + 1200)
    assert t["cost"] == pytest.approx(800 + 800)
    assert t["value"] == pytest.approx(2600)
    assert t["day_pl"] == pytest.approx(50 + 80)
    assert [r["symbol"] for r in p["positions"]] == ["NVDA", "1023.KL"]   # zero-share row dropped, sorted by value
    assert sum(r["weight"] for r in p["positions"]) == pytest.approx(2100 / 2600 * 100)


def test_missing_quote_marks_position_stale():
    p = value_portfolio(HOLDINGS, {}, usdmyr=4.0)
    assert all(r["stale_price"] for r in p["positions"])


def test_fx_passthrough_for_unknown_pair():
    assert FxConverter("MYR", 4.0).to_base(10, "SGD") == 10


def test_history_one_point_per_day():
    h = append_history([{"date": "2026-09-27", "value": 1, "cost": 1, "cash": 0}], "2026-09-28", {"value": 2, "cost": 1, "cash": 0})
    h = append_history(h, "2026-09-28", {"value": 3, "cost": 1, "cash": 0})
    assert [x["value"] for x in h] == [1, 3]


def test_cipher_roundtrip_and_salt_reuse():
    c = AesGcmCipher("correct horse battery staple", iterations=1000)
    a = c.encrypt({"x": 1})
    b = c.encrypt({"x": 2}, previous=a)
    assert c.decrypt(b) == {"x": 2}
    assert a["salt"] == b["salt"] and a["iv"] != b["iv"]
    with pytest.raises(Exception):
        AesGcmCipher("wrong", iterations=1000).decrypt(b)


class FakePrices:
    def __init__(self, frames):
        self.frames = frames

    def history(self, symbols, period="2y"):
        return {s: f for s, f in self.frames.items() if s in symbols}


def test_service_writes_only_ciphertext(tmp_path, frame):
    frames = {"1023.KL": frame([8.5, 9.0]), "NVDA": frame([140.0, 150.0]), "MYR=X": frame([4.0, 4.0])}
    svc = PortfolioService(FakePrices(frames), AesGcmCipher("pw", iterations=1000), DataStore(tmp_path))
    svc.run(HOLDINGS)
    raw = (tmp_path / "portfolio.enc.json").read_text()
    assert "1023" not in raw and "NVDA" not in raw
    data = AesGcmCipher("pw", iterations=1000).decrypt(json.loads(raw))
    assert data["totals"]["value"] == pytest.approx(2600) and len(data["history"]) == 1
