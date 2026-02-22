"""LLM-powered summarization via LiteLLM — implements BaseSummarizer."""

from __future__ import annotations

import os

import litellm

from interfaces.summarizer import BaseSummarizer, SummaryResult

SYSTEM_PROMPT = (
    "You are a factual summarization engine. Given article text, produce a concise, "
    "accurate summary in 2-4 sentences. Preserve key facts, names, and dates. "
    "Do not add opinions or information not present in the source."
)


class Summarizer(BaseSummarizer):
    """Green AI: Generates summaries at the source so 1,000 AI agents
    don't each have to re-process the same raw HTML independently.

    Supports any model backend that LiteLLM routes to (OpenAI, Anthropic,
    local Ollama, etc.) via the LITELLM_MODEL env var.
    """

    def __init__(self, *, model: str | None = None, max_tokens: int = 300) -> None:
        self._model = model or os.getenv("LITELLM_MODEL", "gpt-4o-mini")
        self._max_tokens = max_tokens

    async def summarize(self, text: str, *, hint: str = "") -> SummaryResult:
        user_msg = f"Summarize the following article:\n\n{text[:12000]}"
        if hint:
            user_msg += f"\n\nContext hint: {hint}"

        response = await litellm.acompletion(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=self._max_tokens,
            temperature=0.1,
        )

        choice = response.choices[0]
        return SummaryResult(
            summary=choice.message.content.strip(),
            model=response.model,
            usage_tokens=response.usage.total_tokens,
        )
