"""Gemini daily-brief summarizer (free API key from aistudio.google.com)."""
from __future__ import annotations

import json
import sys

PROMPT = """You write a short daily market brief for a university student in Malaysia who is \
learning about investing. Use ONLY the data below (do not invent numbers or news). \
Plain English, no hype, no buy/sell recommendations.

Format in Markdown, max ~220 words:
**Big picture** – 2 sentences on Malaysia (KLCI, ringgit) and US markets.
**Movers** – 3 bullets on notable watchlist moves and the likely reason if a headline supports it.
**Worth watching** – 2 bullets from the technical signals.
**Concept of the day** – explain ONE term that appears in today's data (e.g. RSI, 200-day average, VIX) in 2 sentences.

DATA (JSON):
{data}"""


class GeminiSummarizer:
    name = "Gemini"
    ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    FALLBACK_MODELS = ("gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash")

    def __init__(self, api_key: str, model: str, http=None, max_chars: int = 24000):
        if http is None:
            import requests
            http = requests
        self.key, self.model, self.http, self.max_chars = api_key, model, http, max_chars

    def summarize(self, brief: dict) -> str | None:
        prompt = PROMPT.format(data=json.dumps(brief, ensure_ascii=False)[: self.max_chars])
        for m in dict.fromkeys((self.model, *self.FALLBACK_MODELS)):
            text = self._call(m, prompt)
            if text:
                return text
        return None

    def _call(self, model: str, prompt: str) -> str | None:
        try:
            r = self.http.post(
                self.ENDPOINT.format(model=model),
                headers={"x-goog-api-key": self.key},   # works for both AIza… and newer AQ.… keys; keeps the key out of URLs
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1200}},
                timeout=90,
            )
            if r.status_code != 200:
                print(f"Gemini {model}: HTTP {r.status_code}", file=sys.stderr)   # never log the key/url
                return None
            parts = r.json()["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts).strip() or None
        except Exception as e:
            print(f"Gemini {model} failed: {type(e).__name__}", file=sys.stderr)
            return None
