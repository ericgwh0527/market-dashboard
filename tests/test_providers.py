from dashboard.news import dedupe, newest_first
from dashboard.providers.google_news import GoogleNewsProvider
from dashboard.providers.yahoo import YahooFundamentalsProvider, YahooNewsProvider, silenced


def test_yahoo_news_parses_both_shapes():
    new = {"content": {"title": "T", "canonicalUrl": {"url": "u"}, "pubDate": "2026-01-01T00:00:00Z", "provider": {"displayName": "R"}}}
    old = {"title": "T2", "link": "u2", "providerPublishTime": 0, "publisher": "P"}
    assert YahooNewsProvider.parse(new)["source"] == "R"
    assert YahooNewsProvider.parse(old)["source"] == "P"
    assert YahooNewsProvider.parse({"content": {}}) is None


def test_fundamentals_units():
    f = YahooFundamentalsProvider.normalise({"dividendYield": 0.05, "profitMargins": 0.2, "trailingPE": 11})
    assert f["div_yield"] == 5 and f["profit_margin"] == 20 and f["pe"] == 11


def test_google_strips_publisher_suffix():
    class Feed:
        entries = [{"title": "Stocks up - The Edge", "source": {"title": "The Edge"}, "link": "l",
                    "published_parsed": (2026, 9, 28, 1, 0, 0, 0, 0, 0)}]
    g = GoogleNewsProvider(parser=lambda url, agent=None: Feed)
    item = g.search("x")[0]
    assert item["title"] == "Stocks up" and item["source"] == "The Edge" and item["published"].startswith("2026-09-28")


def test_dedupe_and_sort():
    items = [{"title": "A b", "published": "2026-01-01T00:00:00Z"}, {"title": "a B!", "published": None},
             {"title": "C", "published": "2026-02-01T00:00:00+00:00"}]
    out = newest_first(dedupe(items))
    assert [i["title"] for i in out] == ["C", "A b"]


def test_silenced_swallows_output(capsys):
    with silenced():
        print("SECRET-TICKER")
    assert "SECRET" not in capsys.readouterr().out
