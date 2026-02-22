"""Copyright opt-out tracking per EU AI Act Article 53.

Publishers can register domains/URLs that opt out of AI training.
This module maintains an append-only log so AI agents can verify
whether content is available for training or restricted to inference-only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class OptOutEntry(BaseModel):
    """A single copyright opt-out declaration."""

    domain: str
    url_pattern: str = "*"
    opt_out_scope: str = Field(
        default="training",
        description="Scope: 'training', 'all', or 'none'",
    )
    declared_by: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    reference: str = Field(
        default="",
        description="Link to the publisher's opt-out declaration (e.g. robots.txt, TDM policy)",
    )


class CopyrightOptOutLog:
    """Append-only log of publisher copyright opt-out declarations.

    Persists to a local JSON-lines file for auditability.
    """

    def __init__(self, log_path: str | Path = "data/copyright_optout.jsonl") -> None:
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: list[OptOutEntry] = []
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            for line in self._path.read_text().strip().splitlines():
                if line.strip():
                    self._entries.append(OptOutEntry.model_validate_json(line))

    def add(self, entry: OptOutEntry) -> None:
        self._entries.append(entry)
        with self._path.open("a") as f:
            f.write(entry.model_dump_json() + "\n")

    def is_opted_out(self, domain: str, url: str = "") -> bool:
        """Check if a domain/URL has opted out of AI training."""
        for entry in self._entries:
            if (
                entry.domain == domain
                and entry.opt_out_scope in ("training", "all")
                and (entry.url_pattern == "*" or url.startswith(entry.url_pattern))
            ):
                return True
        return False

    def get_entries(self, domain: str | None = None) -> list[OptOutEntry]:
        if domain:
            return [e for e in self._entries if e.domain == domain]
        return list(self._entries)

    @property
    def count(self) -> int:
        return len(self._entries)
