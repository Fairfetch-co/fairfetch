"""End-to-end tests simulating both Publisher and AI Agent flows.

These tests exercise the full Green+Legal+Indemnity pipeline from both
sides of the protocol to validate the documented workflows.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from api.negotiation import PreferredAccessHeaders, is_scraper_request
from core.converter import ConversionResult
from core.signatures import Ed25519Signer, Ed25519Verifier
from interfaces.license_provider import UsageGrant
from payments.mock_license_facilitator import MockLicenseProvider


class TestPublisherFlow:
    """Simulates a publisher setting up and verifying their Fairfetch deployment."""

    async def test_health_returns_service_info(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "fairfetch"
        assert "version" in data
        assert "scraper_interceptions" in data

    async def test_402_returned_without_payment(self, client: AsyncClient):
        """Publisher verifies: unauthenticated requests get a 402 with pricing."""
        resp = await client.get("/content/fetch", params={"url": "https://example.com"})
        assert resp.status_code == 402
        body = resp.json()
        assert "accepts" in body
        assert body["accepts"]["asset"] == "USDC"
        assert body["accepts"]["network"] == "base"
        assert "payTo" in body["accepts"]
        assert "price" in body["accepts"]

    async def test_paid_response_includes_all_three_pillars(self, client: AsyncClient):
        """Publisher verifies: paid requests return content with all three pillars."""
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com/article"},
            headers={
                "X-PAYMENT": "test_paid_fairfetch",
                "Accept": "application/ai-context+json",
            },
        )
        assert resp.status_code == 200

        assert "X-Data-Origin-Verified" in resp.headers
        assert resp.headers["X-Data-Origin-Verified"] == "true"

        assert "X-FairFetch-Origin-Signature" in resp.headers
        assert len(resp.headers["X-FairFetch-Origin-Signature"]) > 10

        assert "X-AI-License-Type" in resp.headers

        assert "X-Content-Hash" in resp.headers
        assert resp.headers["X-Content-Hash"].startswith("sha256:")

        assert "X-PAYMENT-RECEIPT" in resp.headers
        assert resp.headers["X-PAYMENT-RECEIPT"].startswith("0x")

        assert "X-Fairfetch-Version" in resp.headers

    async def test_scraper_interception_count_increments(self, client: AsyncClient):
        """Publisher metric: scraper interception count goes up when bots are steered."""
        resp1 = await client.get("/health")
        initial_count = resp1.json()["scraper_interceptions"]

        await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={
                "X-PAYMENT": "test_paid_fairfetch",
                "User-Agent": "GPTBot/1.0",
                "Accept": "text/html",
            },
        )

        resp2 = await client.get("/health")
        new_count = resp2.json()["scraper_interceptions"]
        assert new_count > initial_count


class TestAIAgentFlow:
    """Simulates an AI agent consuming content through Fairfetch."""

    async def test_get_markdown_format(self, client: AsyncClient):
        """Agent requests clean Markdown."""
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com/article"},
            headers={
                "X-PAYMENT": "test_paid_fairfetch",
                "Accept": "text/markdown",
            },
        )
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers["content-type"]
        assert len(resp.text) > 0

    async def test_get_json_ld_format(self, client: AsyncClient):
        """Agent requests JSON-LD knowledge packet."""
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com/article"},
            headers={
                "X-PAYMENT": "test_paid_fairfetch",
                "Accept": "application/ld+json",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["@context"] == "https://schema.org"
        assert body["@type"] == "Article"
        assert "fairfetch:originSignature" in body

    async def test_get_ai_context_format(self, client: AsyncClient):
        """Agent requests full AI context with lineage and grant."""
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com/article"},
            headers={
                "X-PAYMENT": "test_paid_fairfetch",
                "Accept": "application/ai-context+json",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["@context"] == "https://schema.org"
        assert "fairfetch:lineage" in body
        lineage = body["fairfetch:lineage"]
        assert lineage["record_count"] >= 1

    async def test_payment_receipt_returned(self, client: AsyncClient):
        """Agent gets a payment receipt for accounting."""
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={"X-PAYMENT": "test_paid_fairfetch"},
        )
        assert resp.status_code == 200
        receipt = resp.headers.get("X-PAYMENT-RECEIPT", "")
        assert receipt.startswith("0x")
        assert len(receipt) > 10

    async def test_license_id_header_present(self, client: AsyncClient):
        """Agent gets a Usage Grant identifier in response headers."""
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={"X-PAYMENT": "test_paid_fairfetch"},
        )
        assert resp.status_code == 200
        license_id = resp.headers.get("X-FairFetch-License-ID", "")
        assert ":" in license_id

    async def test_summary_endpoint(self, client: AsyncClient):
        """Agent uses the summary endpoint for quick info."""
        resp = await client.get(
            "/content/summary",
            params={"url": "https://example.com"},
            headers={"X-PAYMENT": "test_paid_fairfetch"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "title" in data

    async def test_markdown_endpoint(self, client: AsyncClient):
        """Agent uses the dedicated Markdown endpoint."""
        resp = await client.get(
            "/content/markdown",
            params={"url": "https://example.com"},
            headers={"X-PAYMENT": "test_paid_fairfetch"},
        )
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers["content-type"]


class TestUsageGrantVerification:
    """Tests the Usage Grant workflow that AI agents use for legal indemnity."""

    async def test_grant_roundtrip_issuance_and_verification(self):
        signer = Ed25519Signer()
        provider = MockLicenseProvider(signer)

        grant = await provider.issue_grant(
            content_url="https://publisher.com/article/123",
            content_hash="abcdef1234567890",
            license_type="commercial",
            granted_to="0xAgentWallet",
        )

        assert grant.verify() is True
        assert grant.content_url == "https://publisher.com/article/123"
        assert grant.license_type == "commercial"
        assert grant.granted_to == "0xAgentWallet"

    async def test_grant_manual_verification_with_public_key(self):
        """Simulates an agent manually verifying a grant using only the public key."""
        signer = Ed25519Signer()
        provider = MockLicenseProvider(signer)

        grant = await provider.issue_grant(
            content_url="https://publisher.com/article",
            content_hash="deadbeef",
            license_type="publisher-terms",
            granted_to="agent-1",
        )

        payload = grant.signing_payload()
        verifier = Ed25519Verifier(grant.signature.public_key)
        assert verifier.verify(payload, grant.signature.signature) is True

    async def test_grant_rejects_modified_content_hash(self):
        signer = Ed25519Signer()
        provider = MockLicenseProvider(signer)

        grant = await provider.issue_grant(
            content_url="https://publisher.com/article",
            content_hash="original_hash",
            license_type="publisher-terms",
            granted_to="agent",
        )

        grant.content_hash = "tampered_hash"
        assert grant.verify() is False

    async def test_grant_rejects_modified_url(self):
        signer = Ed25519Signer()
        provider = MockLicenseProvider(signer)

        grant = await provider.issue_grant(
            content_url="https://publisher.com/article",
            content_hash="abc",
            license_type="publisher-terms",
            granted_to="agent",
        )

        grant.content_url = "https://evil.com/stolen"
        assert grant.verify() is False

    async def test_grant_header_value_format(self):
        signer = Ed25519Signer()
        provider = MockLicenseProvider(signer)

        grant = await provider.issue_grant(
            content_url="https://example.com",
            content_hash="test",
            license_type="publisher-terms",
            granted_to="agent",
        )

        header = grant.to_header_value()
        parts = header.split(":")
        assert len(parts) == 2
        assert parts[0] == grant.grant_id


class TestBotSteering:
    """Tests the Direct Pipeline bot-steering behavior."""

    def test_known_crawlers_detected(self):
        crawlers = [
            "GPTBot/1.0",
            "CCBot/2.0",
            "Mozilla/5.0 (compatible; ClaudeBot/1.0)",
            "Amazonbot/0.1",
            "Bytespider",
            "Google-Extended",
            "Perplexity-User/1.0",
        ]
        for ua in crawlers:
            assert is_scraper_request(ua, "text/html") is True, f"Failed to detect: {ua}"

    def test_regular_browsers_not_flagged(self):
        browsers = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
            "curl/8.1.2",
        ]
        for ua in browsers:
            assert is_scraper_request(ua, "text/html") is False, f"False positive: {ua}"

    def test_crawlers_using_fairfetch_not_flagged(self):
        assert is_scraper_request("GPTBot/1.0", "application/ai-context+json") is False
        assert is_scraper_request("CCBot/2.0", "application/ld+json") is False
        assert is_scraper_request("ClaudeBot/1.0", "text/markdown") is False

    def test_preferred_access_headers_structure(self):
        headers = PreferredAccessHeaders(
            llms_txt_url="/.well-known/llms.txt",
            mcp_endpoint="/mcp",
        )
        d = headers.to_dict()
        assert d["X-FairFetch-Preferred-Access"] == "mcp+json-ld"
        assert d["X-FairFetch-LLMS-Txt"] == "/.well-known/llms.txt"
        assert d["X-FairFetch-MCP-Endpoint"] == "/mcp"
        assert 'rel="ai-policy"' in d["Link"]
        assert 'rel="ai-content-api"' in d["Link"]

    async def test_scraper_gets_steering_headers_on_content_endpoint(self, client: AsyncClient):
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={
                "X-PAYMENT": "test_paid_fairfetch",
                "User-Agent": "GPTBot/1.0",
                "Accept": "text/html",
            },
        )
        assert resp.headers.get("X-FairFetch-Preferred-Access") == "mcp+json-ld"
        assert "Link" in resp.headers

    async def test_normal_agent_no_steering_headers(self, client: AsyncClient):
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={
                "X-PAYMENT": "test_paid_fairfetch",
                "Accept": "application/ai-context+json",
            },
        )
        assert resp.headers.get("X-FairFetch-Preferred-Access") is None


class TestContentNegotiationEdgeCases:
    """Edge cases for content negotiation the documentation mentions."""

    async def test_wildcard_accept_returns_json(self, client: AsyncClient):
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={
                "X-PAYMENT": "test_paid_fairfetch",
                "Accept": "*/*",
            },
        )
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")

    async def test_no_accept_header_returns_json(self, client: AsyncClient):
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={"X-PAYMENT": "test_paid_fairfetch"},
        )
        assert resp.status_code == 200


class TestX402FlowEdgeCases:
    """Edge cases around the x402 payment flow."""

    async def test_any_test_prefix_accepted(self, client: AsyncClient):
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={"X-PAYMENT": "test_any_value_works"},
        )
        assert resp.status_code == 200

    async def test_no_prefix_rejected(self, client: AsyncClient):
        resp = await client.get(
            "/content/fetch",
            params={"url": "https://example.com"},
            headers={"X-PAYMENT": "not_a_test_token"},
        )
        assert resp.status_code == 402
        body = resp.json()
        assert "verification_error" in body

    async def test_exempt_paths_no_payment(self, client: AsyncClient):
        """Health and docs endpoints are exempt from payment."""
        for path in ["/health", "/docs", "/redoc"]:
            resp = await client.get(path)
            assert resp.status_code != 402, f"{path} should be exempt from payment"
