"""Search engine allow/block list for free indexing (usage category search_engine_indexing)."""

from __future__ import annotations


def is_allowed_search_engine(
    user_agent: str,
    allowed: list[str],
    blocked: list[str],
) -> bool:
    """True if UA matches an allowed search engine and is not in the blocklist."""
    ua = (user_agent or "").strip()
    if not ua:
        return False
    ua_lower = ua.lower()
    for sub in blocked:
        if sub.strip().lower() in ua_lower:
            return False
    return any(sub.strip().lower() in ua_lower for sub in allowed)
