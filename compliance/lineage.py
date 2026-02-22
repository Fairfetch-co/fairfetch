"""Data lineage tracking for EU AI Act compliance.

Records the full provenance chain: where content was sourced, how it was
processed, and what transformations were applied before serving to AI agents.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class LineageRecord(BaseModel):
    """A single step in the data lineage chain."""

    step: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    tool: str = ""
    input_hash: str = ""
    output_hash: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class DataLineageTracker:
    """Accumulates lineage records through the content processing pipeline.

    Example::

        tracker = DataLineageTracker(source_url="https://example.com/article")
        tracker.record("fetch", tool="httpx", output_hash=hash_of_html)
        tracker.record(
            "extract", tool="trafilatura",
            input_hash=hash_of_html, output_hash=hash_of_md,
        )
        tracker.record(
            "summarize", tool="litellm/gpt-4o-mini",
            input_hash=hash_of_md, output_hash=hash_of_summary,
        )
        lineage = tracker.to_dict()
    """

    def __init__(self, source_url: str) -> None:
        self._source_url = source_url
        self._records: list[LineageRecord] = []

    def record(
        self,
        step: str,
        *,
        tool: str = "",
        input_hash: str = "",
        output_hash: str = "",
        **extra: str,
    ) -> None:
        self._records.append(
            LineageRecord(
                step=step,
                tool=tool,
                input_hash=input_hash,
                output_hash=output_hash,
                metadata=extra,
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "source_url": self._source_url,
            "pipeline": [r.model_dump() for r in self._records],
            "record_count": len(self._records),
        }

    @staticmethod
    def hash_content(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()
