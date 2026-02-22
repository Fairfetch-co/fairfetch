"""Tests for the MCP server tools — validates Green+Legal+Indemnity via Direct Pipeline."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from core.converter import ConversionResult

MOCK_CONVERSION = ConversionResult(
    markdown="# Test Article\n\nThis is test content about climate change.",
    title="Test Article",
    author="Dr. Test",
    date="2026-01-15",
    url="https://example.com/test",
)


MOCK_SUMMARY_RESPONSE = AsyncMock()
MOCK_SUMMARY_RESPONSE.choices = [
    AsyncMock(message=AsyncMock(content="A concise summary of the test article."))
]
MOCK_SUMMARY_RESPONSE.model = "test-model"
MOCK_SUMMARY_RESPONSE.usage = AsyncMock(total_tokens=42)


class TestMCPTools:
    @patch("mcp_server.server._converter")
    @patch("core.summarizer.litellm.acompletion", return_value=MOCK_SUMMARY_RESPONSE)
    async def test_get_site_summary(self, mock_llm, mock_converter):
        mock_converter.from_url = AsyncMock(return_value=MOCK_CONVERSION)

        from mcp_server.server import get_site_summary

        result = await get_site_summary("https://example.com/test")
        data = json.loads(result)

        assert data["title"] == "Test Article"
        assert data["author"] == "Dr. Test"
        assert "summary" in data
        assert data["origin_verified"] is True
        assert "signature" in data
        assert "usage_grant" in data
        assert "grant_id" in data["usage_grant"]

    @patch("mcp_server.server._converter")
    async def test_fetch_article_markdown(self, mock_converter):
        mock_converter.from_url = AsyncMock(return_value=MOCK_CONVERSION)

        from mcp_server.server import fetch_article_markdown

        result = await fetch_article_markdown("https://example.com/test")

        assert "# Test Article" in result
        assert "Source:" in result
        assert "Dr. Test" in result
        assert "climate change" in result

    @patch("mcp_server.server._converter")
    @patch("core.summarizer.litellm.acompletion", return_value=MOCK_SUMMARY_RESPONSE)
    async def test_get_verified_facts(self, mock_llm, mock_converter):
        mock_converter.from_url = AsyncMock(return_value=MOCK_CONVERSION)

        from mcp_server.server import get_verified_facts

        result = await get_verified_facts("https://example.com/test")
        data = json.loads(result)

        assert data["@context"] == "https://schema.org"
        assert data["@type"] == "Article"
        assert "fairfetch:originSignature" in data
        assert "fairfetch:lineage" in data
        assert data["fairfetch:lineage"]["record_count"] == 2

        assert "fairfetch:usageGrant" in data
        grant = data["fairfetch:usageGrant"]
        assert "grant_id" in grant
        assert grant["valid"] is True
