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


def test_gemini_sends_key_in_header_not_url():
    from dashboard.providers.gemini import GeminiSummarizer
    calls = []

    class Resp:
        status_code = 200
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "brief"}]}}]}

    class Http:
        def post(self, url, **kw):
            calls.append((url, kw))
            return Resp()

    out = GeminiSummarizer("AQ.Ab-test", "gemini-2.5-flash", http=Http()).summarize({"x": 1})
    url, kw = calls[0]
    assert out == "brief" and "AQ." not in url and kw["headers"]["x-goog-api-key"] == "AQ.Ab-test" and "params" not in kw


class _Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body = status, body or {}
    def json(self):
        return self._body


def _ok(text, reason="STOP"):
    return _Resp(200, {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": reason}]})


def test_gemini_discards_truncated_answer_and_tries_next_model():
    from dashboard.providers.gemini import GeminiSummarizer
    replies = iter([_ok("cut off at", "MAX_TOKENS"), _ok("full brief")])

    class Http:
        def post(self, url, **kw):
            assert kw["json"]["generationConfig"]["maxOutputTokens"] >= 4096
            return next(replies)

    assert GeminiSummarizer("k", "gemini-2.5-flash", http=Http()).summarize({}) == "full brief"


def test_gemini_retries_without_thinking_config_on_400():
    from dashboard.providers.gemini import GeminiSummarizer
    seen = []

    class Http:
        def post(self, url, **kw):
            cfg = kw["json"]["generationConfig"]
            seen.append("thinkingConfig" in cfg)
            return _Resp(400) if "thinkingConfig" in cfg else _ok("ok")

    assert GeminiSummarizer("k", "gemini-2.0-flash", http=Http()).summarize({}) == "ok"
    assert seen == [True, False]


def test_gemini_caps_requests_and_records_safe_status():
    from dashboard.providers.gemini import GeminiSummarizer
    calls = []

    class Http:
        def post(self, url, **kw):
            calls.append(url)
            return _Resp(429, {"error": {"status": "RESOURCE_EXHAUSTED", "message": "quota"}})

    g = GeminiSummarizer("AQ.secret-key", "gemini-2.5-flash", http=Http())
    assert g.summarize({}) is None
    assert len(calls) <= GeminiSummarizer.MAX_REQUESTS
    assert g.status["ok"] is False and "RESOURCE_EXHAUSTED" in g.status["attempts"][0]
    assert "secret" not in str(g.status)
