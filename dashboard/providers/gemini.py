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
    MAX_REQUESTS = 4          # hard cap per run, so failures can't burn the free quota

    # Gemini 2.5+ "thinks" before answering and those tokens count against
    # maxOutputTokens – with a small limit the brief got cut off mid-sentence.
    # So: turn thinking off where supported, allow plenty of tokens, and only
    # accept answers that finished normally (finishReason STOP).
    MAX_OUTPUT_TOKENS = 4096
    GENERATION_VARIANTS = (
        {"thinkingConfig": {"thinkingBudget": 0}},   # 2.5 Flash: no thinking
        {},                                          # models that reject thinkingConfig
    )

    def __init__(self, api_key: str, model: str, http=None, max_chars: int = 24000):
        if http is None:
            import requests
            http = requests
        self.key, self.model, self.http, self.max_chars = api_key, model, http, max_chars
        self.attempts: list[str] = []   # public-safe diagnostics, e.g. "gemini-2.5-flash: RESOURCE_EXHAUSTED"
        self.used_model: str | None = None

    @property
    def status(self) -> dict:
        return {"ok": self.used_model is not None, "model": self.used_model, "attempts": self.attempts}

    def summarize(self, brief: dict) -> str | None:
        prompt = PROMPT.format(data=json.dumps(brief, ensure_ascii=False)[: self.max_chars])
        self.attempts, self.used_model = [], None
        for m in dict.fromkeys((self.model, *self.FALLBACK_MODELS)):
            if len(self.attempts) >= self.MAX_REQUESTS:
                break
            text = self._call(m, prompt)
            if text:
                self.used_model = m
                return text
        return None

    def _call(self, model: str, prompt: str) -> str | None:
        for extra in self.GENERATION_VARIANTS:
            if len(self.attempts) >= self.MAX_REQUESTS:
                return None
            config = {"temperature": 0.4, "maxOutputTokens": self.MAX_OUTPUT_TOKENS, **extra}
            try:
                r = self.http.post(
                    self.ENDPOINT.format(model=model),
                    headers={"x-goog-api-key": self.key},   # works for AIza… and AQ.… keys; keeps the key out of URLs
                    json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": config},
                    timeout=90,
                )
            except Exception as e:
                self._note(model, type(e).__name__)
                return None
            if r.status_code == 400 and extra:
                self._note(model, "HTTP 400 with thinkingConfig – retrying without")
                continue
            if r.status_code != 200:
                self._note(model, f"HTTP {r.status_code} {self._error_status(r)}".strip())
                return None                                  # 429/404 etc.: move on to the next model
            return self._complete_text(model, r.json())
        return None

    def _note(self, model: str, what: str) -> None:
        line = f"{model}: {what}"
        self.attempts.append(line)
        print(f"Gemini {line}", file=sys.stderr)             # never logs the key

    @staticmethod
    def _error_status(r) -> str:
        """Google's error code word (e.g. RESOURCE_EXHAUSTED, NOT_FOUND) – safe to publish."""
        try:
            return str(r.json()["error"]["status"])[:40]
        except Exception:
            return ""

    def _complete_text(self, model: str, body: dict) -> str | None:
        try:
            cand = body["candidates"][0]
            text = "".join(p.get("text", "") for p in cand["content"]["parts"]).strip()
        except (KeyError, IndexError, TypeError):
            self._note(model, "unexpected response shape")
            return None
        reason = cand.get("finishReason", "STOP")
        if reason != "STOP":
            self._note(model, f"incomplete answer (finishReason={reason}) – discarded")
            return None
        self.attempts.append(f"{model}: ok")
        return text or None
