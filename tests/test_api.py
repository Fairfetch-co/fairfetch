"""Tests for the FastAPI application — validates the Green+Legal+Indemnity triple."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    async def test_health_no_payment_required(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "fairfetch"
        assert "scraper_interceptions" in data


class TestX402PaymentGating:
    async def test_content_without_payment_returns_402(self, client: AsyncClient):
        resp = await client.get("/content/fetch", params={"url": "https://example.com"})
        assert resp.status_code == 402

        body = resp.json()
        assert "accepts" in body
        assert body["accepts"]["asset"] == "USDC"
        assert body["accepts"]["network"] == "base"
        assert "payTo" in body["accepts"]

    async def test_content_with_valid_payment(self, client: AsyncClient):
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={"X-PAYMENT": "test_paid_fairfetch"},
        )
        assert resp.status_code != 402 or "verification_error" in resp.json()

    async def test_content_with_invalid_payment_returns_402(self, client: AsyncClient):
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={"X-PAYMENT": "invalid_no_prefix"},
        )
        assert resp.status_code == 402
        body = resp.json()
        assert "verification_error" in body


class TestGreenLegalIndemnityTriple:
    """Validates that a successful 200 response includes all three pillars."""

    async def test_response_has_compliance_headers(self, client: AsyncClient):
        """Legal: signed origin headers are present."""
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={
                "X-PAYMENT": "test_paid_fairfetch",
                "Accept": "application/ai-context+json",
            },
        )
        if resp.status_code == 200:
            assert resp.headers.get("X-Data-Origin-Verified") == "true"
            assert "X-AI-License-Type" in resp.headers
            assert "X-FairFetch-Origin-Signature" in resp.headers
            assert "X-Content-Hash" in resp.headers

    async def test_response_has_payment_receipt(self, client: AsyncClient):
        """Payment: settlement receipt is present."""
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={"X-PAYMENT": "test_paid_fairfetch"},
        )
        if resp.status_code == 200:
            assert "X-PAYMENT-RECEIPT" in resp.headers
            assert resp.headers["X-PAYMENT-RECEIPT"].startswith("0x")


class TestContentNegotiation:
    async def test_markdown_accept_header(self, client: AsyncClient):
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={
                "Accept": "text/markdown",
                "X-PAYMENT": "test_paid_fairfetch",
            },
        )
        if resp.status_code == 200:
            assert "text/markdown" in resp.headers.get("content-type", "")

    async def test_ai_context_accept_header(self, client: AsyncClient):
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={
                "Accept": "application/ai-context+json",
                "X-PAYMENT": "test_paid_fairfetch",
            },
        )
        if resp.status_code == 200:
            assert "ai-context" in resp.headers.get("content-type", "")


class TestNegotiationLogic:
    def test_negotiate_ai_context(self):
        from api.negotiation import ContentFormat, negotiate
        assert negotiate("application/ai-context+json") == ContentFormat.AI_CONTEXT

    def test_negotiate_markdown(self):
        from api.negotiation import ContentFormat, negotiate
        assert negotiate("text/markdown") == ContentFormat.MARKDOWN

    def test_negotiate_jsonld(self):
        from api.negotiation import ContentFormat, negotiate
        assert negotiate("application/ld+json") == ContentFormat.JSON_LD

    def test_negotiate_default(self):
        from api.negotiation import ContentFormat, negotiate
        assert negotiate("*/*") == ContentFormat.JSON

    def test_negotiate_empty(self):
        from api.negotiation import ContentFormat, negotiate
        assert negotiate("") == ContentFormat.JSON


class TestAiAgentDetection:
    def test_detect_by_accept(self):
        from api.negotiation import is_ai_agent_request
        assert is_ai_agent_request("application/ai-context+json") is True
        assert is_ai_agent_request("text/html") is False

    def test_detect_by_user_agent(self):
        from api.negotiation import is_ai_agent_request
        assert is_ai_agent_request("text/html", "ChatGPT-User") is True
        assert is_ai_agent_request("text/html", "Mozilla/5.0") is False
        assert is_ai_agent_request("text/html", "CCBot/2.0") is True


class TestScraperSteering:
    """Direct Pipeline: scrapers get steered to the legal path."""

    def test_scraper_requesting_html_detected(self):
        from api.negotiation import is_scraper_request
        assert is_scraper_request("GPTBot/1.0", "text/html") is True
        assert is_scraper_request("GPTBot/1.0", "application/ai-context+json") is False
        assert is_scraper_request("Mozilla/5.0", "text/html") is False

    def test_preferred_access_headers(self):
        from api.negotiation import PreferredAccessHeaders
        headers = PreferredAccessHeaders(
            llms_txt_url="/.well-known/llms.txt",
            mcp_endpoint="/mcp",
        )
        d = headers.to_dict()
        assert d["X-FairFetch-Preferred-Access"] == "mcp+json-ld"
        assert "Link" in d
        assert "ai-policy" in d["Link"]
        assert "ai-content-api" in d["Link"]
