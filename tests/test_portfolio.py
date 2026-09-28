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


class FakeQuotes:
    def __init__(self, table):
        self.table = table

    def quotes(self, symbols):
        return {s: self.table[s] for s in symbols if s in self.table}


def test_service_writes_only_ciphertext(tmp_path):
    table = {"1023.KL": Quote(9.0, 8.5), "NVDA": Quote(150.0, 140.0), "MYR=X": Quote(4.0, 4.0)}
    svc = PortfolioService(FakeQuotes(table), AesGcmCipher("pw", iterations=1000), DataStore(tmp_path))
    svc.run(HOLDINGS)
    raw = (tmp_path / "portfolio.enc.json").read_text()
    assert "1023" not in raw and "NVDA" not in raw
    data = AesGcmCipher("pw", iterations=1000).decrypt(json.loads(raw))
    assert data["totals"]["value"] == pytest.approx(2600) and len(data["history"]) == 1


def test_service_keeps_previous_file_when_prices_are_down(tmp_path):
    from dashboard.portfolio.service import NoQuotes
    svc = PortfolioService(FakeQuotes({}), AesGcmCipher("pw", iterations=1000), DataStore(tmp_path))
    with pytest.raises(NoQuotes):
        svc.run(HOLDINGS)
    assert not (tmp_path / "portfolio.enc.json").exists()


def test_yahoo_chart_parsing_and_silence(capsys):
    from dashboard.portfolio.quotes import YahooChartQuotes, parse_chart
    body = {"chart": {"result": [{"timestamp": [1759000000, 1759086400, 1759172800],
                                   "indicators": {"quote": [{"close": [2.7, 2.77, None]}]}}]}}
    q = parse_chart(body)
    assert q.price == 2.77 and q.prev == 2.7
    assert parse_chart({"chart": {"result": None}}) is None

    def boom(url):
        raise OSError("SECRET-5227.KL")
    got = YahooChartQuotes(fetch=boom, pause=0).quotes(["5227.KL"])
    assert got == {} and "5227" not in capsys.readouterr().out + capsys.readouterr().err


def test_portfolio_modules_avoid_heavy_dependencies():
    """The passphrase job installs only `cryptography`; importing must not need pandas/yfinance."""
    import subprocess, sys, textwrap
    code = textwrap.dedent("""
        import sys, builtins
        real = builtins.__import__
        def guard(name, *a, **k):
            if name.split('.')[0] in {'pandas', 'yfinance', 'numpy', 'feedparser', 'requests'}:
                raise ImportError('blocked ' + name)
            return real(name, *a, **k)
        builtins.__import__ = guard
        import dashboard.portfolio.service, dashboard.portfolio.quotes, dashboard.portfolio.crypto
        print('ok')
    """)
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    out = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True)
    assert out.stdout.strip() == "ok", out.stderr
