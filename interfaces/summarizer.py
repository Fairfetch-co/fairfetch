"""BaseSummarizer — abstract interface for content summarization.

Part of the FairFetch Open Standard. Decouples the summarization strategy
from the rest of the pipeline so implementations can use any backend
(LiteLLM, local Ollama, a custom extractive summarizer, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SummaryResult:
    summary: str
    model: str
    usage_tokens: int


class BaseSummarizer(ABC):
    """Abstract summarizer that any LLM or extractive backend can implement."""

    @abstractmethod
    async def summarize(self, text: str, *, hint: str = "") -> SummaryResult:
        """Produce a concise summary of the given text."""
        ...
