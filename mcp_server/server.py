"""Fairfetch MCP Server — the Direct Pipeline for AI agents.

Exposes content from Fairfetch-enabled sites as MCP Tools and Resources. This is the
"Official Legal Path" — AI agents that use this endpoint get
cryptographically signed content with Usage Grants for legal indemnity.

Run standalone:       python -m mcp_server.server
Test with inspector:  npx @modelcontextprotocol/inspector python -m mcp_server.server
"""

from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from compliance.lineage import DataLineageTracker
from core.converter import ContentConverter
from core.knowledge_packet import KnowledgePacketBuilder
from core.signatures import Ed25519Signer
from core.summarizer import Summarizer
from interfaces.license_provider import BaseLicenseProvider, UsageCategory
from payments.mock_license_facilitator import MockLicenseProvider

mcp = FastMCP(
    "Fairfetch",
    instructions=(
        "Direct Pipeline to content from Fairfetch-enabled sites. Get verified, machine-ready "
        "articles with cryptographic Usage Grants — the legal-safe alternative "
        "to web scraping."
    ),
)

_signer = Ed25519Signer(os.getenv("FAIRFETCH_SIGNING_KEY") or None)
_converter = ContentConverter()
_packet_builder = KnowledgePacketBuilder(signer=_signer)
_license_provider: BaseLicenseProvider = MockLicenseProvider(_signer)


def _get_summarizer() -> Summarizer:
    return Summarizer(model=os.getenv("LITELLM_MODEL", "gpt-4o-mini"))


@mcp.tool()
async def get_site_summary(
    url: str,
    usage: str = UsageCategory.SUMMARY,
) -> str:
    """Fetch a web page and return a concise AI-generated summary with legal provenance.

    Returns a signed summary with a Usage Grant token that proves legal access.

    Args:
        url: The URL of the article or page to summarize.
        usage: Usage category (search_engine_indexing, summary, rag, research, training, commercial)
                Controls the compliance level and pricing tier.

    Returns:
        JSON with title, author, summary, origin signature, and usage grant.
    """
    try:
        usage_cat = UsageCategory(usage.lower())
    except ValueError:
        usage_cat = UsageCategory.SUMMARY

    result = await _converter.from_url(url)
    summarizer = _get_summarizer()
    summary_result = await summarizer.summarize(result.markdown)

    sig = _signer.sign(result.markdown.encode())
    content_hash = BaseLicenseProvider.hash_content(result.markdown)

    grant = await _license_provider.issue_grant(
        content_url=url,
        content_hash=content_hash,
        license_type="publisher-terms",
        usage_category=usage_cat.value,
        granted_to="mcp-agent",
    )

    return json.dumps(
        {
            "url": url,
            "title": result.title,
            "author": result.author,
            "date": result.date,
            "summary": summary_result.summary,
            "model_used": summary_result.model,
            "origin_verified": True,
            "signature": sig.signature,
            "public_key": sig.public_key,
            "usage_category": usage_cat.value,
            "usage_grant": {
                "grant_id": grant.grant_id,
                "license_type": grant.license_type,
                "usage_category": grant.usage_category,
                "granted_at": grant.granted_at,
                "content_hash": grant.content_hash,
                "signature": grant.signature.signature if grant.signature else None,
                "verify_with_public_key": (grant.signature.public_key if grant.signature else None),
            },
        },
        indent=2,
    )


@mcp.tool()
async def fetch_article_markdown(url: str) -> str:
    """Fetch a web page and return its content as clean Markdown (Green AI).

    Pre-processed at the source — eliminates redundant crawling compute.

    Args:
        url: The URL of the article to convert.

    Returns:
        Clean Markdown text with source attribution header.
    """
    result = await _converter.from_url(url)

    header = f"# {result.title or 'Untitled'}\n\n**Source:** {url}\n"
    if result.author:
        header += f"**Author:** {result.author}\n"
    if result.date:
        header += f"**Date:** {result.date}\n"
    header += "\n---\n\n"

    return header + result.markdown


@mcp.tool()
async def get_verified_facts(
    url: str,
    usage: str = UsageCategory.RAG,
) -> str:
    """Fetch a web page and return a signed knowledge packet with full data lineage.

    Includes: cryptographic proof of origin (Ed25519), content hash,
    complete data lineage chain (EU AI Act), and a Usage Grant for indemnity.

    Args:
        url: The URL of the content to verify.
        usage: Usage category (search_engine_indexing, summary, rag, research, training, commercial)
                Controls the compliance level and pricing tier.

    Returns:
        A JSON-LD knowledge packet with signature, lineage, and usage grant.
    """
    try:
        usage_cat = UsageCategory(usage.lower())
    except ValueError:
        usage_cat = UsageCategory.RAG

    tracker = DataLineageTracker(source_url=url)

    result = await _converter.from_url(url)
    md_hash = DataLineageTracker.hash_content(result.markdown)
    tracker.record("extract", tool="trafilatura", output_hash=md_hash)

    summarizer = _get_summarizer()
    summary_result = await summarizer.summarize(result.markdown)
    summary_hash = DataLineageTracker.hash_content(summary_result.summary)
    tracker.record(
        "summarize",
        tool=f"litellm/{summary_result.model}",
        input_hash=md_hash,
        output_hash=summary_hash,
    )

    packet = _packet_builder.build(
        markdown=result.markdown,
        summary=summary_result.summary,
        title=result.title or "",
        author=result.author or "",
        url=url,
        date=result.date or "",
        usage_category=usage_cat.value,
    )

    grant = await _license_provider.issue_grant(
        content_url=url,
        content_hash=md_hash,
        license_type="publisher-terms",
        usage_category=usage_cat.value,
        granted_to="mcp-agent",
    )

    output = packet.to_jsonld()
    output["fairfetch:lineage"] = tracker.to_dict()
    output["fairfetch:usageGrant"] = {
        "grant_id": grant.grant_id,
        "license_type": grant.license_type,
        "usage_category": grant.usage_category,
        "content_hash": grant.content_hash,
        "granted_at": grant.granted_at,
        "valid": grant.verify(),
    }

    return json.dumps(output, indent=2)


# --- Resources ---


@mcp.resource("fairfetch://config")
async def get_config() -> str:
    """Current Fairfetch server configuration (non-sensitive)."""
    from interfaces.license_provider import USAGE_CATEGORY_META

    usage_tiers = {
        cat.value: {
            "compliance_level": str(meta["compliance_level"]),
            "price_multiplier": meta["price_multiplier"],
            "description": str(meta["description"]),
        }
        for cat, meta in USAGE_CATEGORY_META.items()
    }

    return json.dumps(
        {
            "version": "0.2.0",
            "test_mode": os.getenv("FAIRFETCH_TEST_MODE", "true"),
            "model": os.getenv("LITELLM_MODEL", "gpt-4o-mini"),
            "public_key": _signer.public_key_b64,
            "supported_formats": [
                "text/markdown",
                "application/ai-context+json",
                "application/ld+json",
            ],
            "usage_categories": usage_tiers,
            "pillars": ["green-ai", "legal-safe-harbor", "direct-pipeline"],
        },
        indent=2,
    )


@mcp.resource("fairfetch://public-key")
async def get_public_key() -> str:
    """The Ed25519 public key used to sign content and usage grants."""
    return _signer.public_key_b64


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
