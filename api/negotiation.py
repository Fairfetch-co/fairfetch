"""Content negotiation and Direct Pipeline bot-steering logic.

Supports standard media types plus the custom 'application/ai-context+json'.
Implements Preferred-Access headers that steer scrapers toward the
official legal path (MCP/JSON-LD) instead of raw HTML crawling.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ContentFormat(str, Enum):
    MARKDOWN = "text/markdown"
    JSON_LD = "application/ld+json"
    AI_CONTEXT = "application/ai-context+json"
    HTML = "text/html"
    JSON = "application/json"
    PLAIN = "text/plain"


AI_AGENT_ACCEPT_TYPES = {
    ContentFormat.AI_CONTEXT,
    ContentFormat.JSON_LD,
    ContentFormat.MARKDOWN,
}

_ACCEPT_PRIORITY: list[ContentFormat] = [
    ContentFormat.AI_CONTEXT,
    ContentFormat.JSON_LD,
    ContentFormat.MARKDOWN,
    ContentFormat.JSON,
    ContentFormat.HTML,
    ContentFormat.PLAIN,
]

KNOWN_CRAWLER_UAS = [
    "chatgpt", "claude", "anthropic", "openai", "perplexity",
    "google-extended", "gptbot", "ccbot", "cohere-ai",
    "bytespider", "claudebot", "ia_archiver", "amazonbot",
    "facebookexternalhit", "twitterbot", "applebot",
    "diffbot", "semrushbot", "ahrefsbot", "mj12bot",
    "dotbot", "petalbot", "barkrowler",
]


def negotiate(accept_header: str) -> ContentFormat:
    """Parse the Accept header and return the best matching format.

    Priority: ai-context+json > ld+json > markdown > json > html > plain
    """
    if not accept_header or accept_header == "*/*":
        return ContentFormat.JSON

    normalized = accept_header.lower().strip()

    for fmt in _ACCEPT_PRIORITY:
        if fmt.value in normalized:
            return fmt

    if "markdown" in normalized or "text/md" in normalized:
        return ContentFormat.MARKDOWN

    return ContentFormat.JSON


def is_ai_agent_request(accept_header: str, user_agent: str = "") -> bool:
    """Heuristic to detect AI agent requests based on headers."""
    if any(t.value in accept_header.lower() for t in AI_AGENT_ACCEPT_TYPES):
        return True

    ua_lower = user_agent.lower()
    return any(p in ua_lower for p in KNOWN_CRAWLER_UAS)


def is_scraper_request(user_agent: str, accept_header: str = "") -> bool:
    """Detect non-FairFetch crawlers requesting raw HTML — candidates for steering."""
    ua_lower = user_agent.lower()
    is_known_crawler = any(p in ua_lower for p in KNOWN_CRAWLER_UAS)
    is_requesting_html = not accept_header or "text/html" in accept_header.lower()
    is_not_using_fairfetch = not any(
        t.value in accept_header.lower() for t in AI_AGENT_ACCEPT_TYPES
    )
    return is_known_crawler and is_requesting_html and is_not_using_fairfetch


@dataclass(frozen=True, slots=True)
class PreferredAccessHeaders:
    """Headers injected into responses to scrapers, steering them to the legal API path."""

    llms_txt_url: str
    mcp_endpoint: str
    api_base: str = ""

    def to_dict(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "X-FairFetch-Preferred-Access": "mcp+json-ld",
            "X-FairFetch-LLMS-Txt": self.llms_txt_url,
            "X-FairFetch-MCP-Endpoint": self.mcp_endpoint,
            "Link": (
                f'<{self.llms_txt_url}>; rel="ai-policy", '
                f'<{self.mcp_endpoint}>; rel="ai-content-api"'
            ),
        }
        if self.api_base:
            headers["X-FairFetch-API"] = self.api_base
        return headers
