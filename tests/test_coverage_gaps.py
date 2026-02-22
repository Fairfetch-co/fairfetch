"""Tests targeting specific uncovered lines to push toward 100% coverage.

Each test is annotated with the file:line it covers.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from compliance.copyright import CopyrightOptOutLog, OptOutEntry
from compliance.headers import ComplianceHeaders
from core.converter import ContentConverter, ConversionResult
from core.signatures import Ed25519Signer
from interfaces.license_provider import UsageGrant
from payments.mock_license_facilitator import MockLicenseProvider, _extract_domain


# --- api/negotiation.py:62-65 — fallback branches in negotiate() ---

class TestNegotiationFallbacks:
    def test_negotiate_text_md(self):
        """Covers negotiation.py:62 — 'text/md' Accept header."""
        from api.negotiation import ContentFormat, negotiate
        assert negotiate("text/md") == ContentFormat.MARKDOWN

    def test_negotiate_markdown_word(self):
        """Covers negotiation.py:62 — bare 'markdown' in Accept header."""
        from api.negotiation import ContentFormat, negotiate
        assert negotiate("markdown") == ContentFormat.MARKDOWN

    def test_negotiate_unknown_returns_json(self):
        """Covers negotiation.py:65 — unknown Accept header falls back to JSON."""
        from api.negotiation import ContentFormat, negotiate
        assert negotiate("application/xml") == ContentFormat.JSON


# --- api/negotiation.py:107 — PreferredAccessHeaders with api_base ---

class TestPreferredAccessWithApiBase:
    def test_api_base_header_included(self):
        """Covers negotiation.py:107 — api_base field produces X-FairFetch-API header."""
        from api.negotiation import PreferredAccessHeaders
        headers = PreferredAccessHeaders(
            llms_txt_url="/.well-known/llms.txt",
            mcp_endpoint="/mcp",
            api_base="https://api.example.com",
        )
        d = headers.to_dict()
        assert d["X-FairFetch-API"] == "https://api.example.com"


# --- compliance/headers.py:41 — lineage_url set ---

class TestComplianceLineageUrl:
    def test_lineage_url_header(self):
        """Covers headers.py:41 — X-Content-Lineage header when lineage_url is set."""
        headers = ComplianceHeaders(lineage_url="https://example.com/lineage/123")
        d = headers.to_dict()
        assert d["X-Content-Lineage"] == "https://example.com/lineage/123"


# --- compliance/copyright.py:70 — get_entries without domain filter ---

class TestCopyrightGetAllEntries:
    def test_get_entries_no_filter(self, tmp_path: Path):
        """Covers copyright.py:70 — get_entries() with no domain returns all."""
        log = CopyrightOptOutLog(log_path=tmp_path / "optout.jsonl")
        log.add(OptOutEntry(domain="a.com", opt_out_scope="training"))
        log.add(OptOutEntry(domain="b.com", opt_out_scope="all"))

        all_entries = log.get_entries()
        assert len(all_entries) == 2


# --- core/summarizer.py:33 — summarize() with hint parameter ---

class TestSummarizerHint:
    async def test_summarize_with_hint(self):
        """Covers summarizer.py:33 — hint appended to prompt."""
        mock_response = AsyncMock()
        mock_response.choices = [
            AsyncMock(message=AsyncMock(content="Summary with hint context."))
        ]
        mock_response.model = "test-model"
        mock_response.usage = AsyncMock(total_tokens=30)

        with patch("core.summarizer.litellm.acompletion", return_value=mock_response) as mock_call:
            from core.summarizer import Summarizer
            s = Summarizer(model="test")
            result = await s.summarize("Some article text", hint="Focus on climate")
            assert result.summary == "Summary with hint context."
            call_args = mock_call.call_args
            user_msg = call_args.kwargs["messages"][1]["content"]
            assert "Focus on climate" in user_msg


# --- interfaces/license_provider.py:59 — verify() with no signature ---

class TestGrantNoSignature:
    def test_unsigned_grant_fails_verification(self):
        """Covers license_provider.py:58-59 — verify returns False when signature is None."""
        grant = UsageGrant(
            content_url="https://example.com",
            content_hash="abc",
            license_type="publisher-terms",
            granted_to="agent",
            signature=None,
        )
        assert grant.verify() is False


# --- payments/mock_license_facilitator.py:48 — public_key_b64 property ---

class TestMockLicenseProviderPublicKey:
    def test_public_key_accessible(self):
        """Covers mock_license_facilitator.py:48 — public_key_b64 property."""
        signer = Ed25519Signer()
        provider = MockLicenseProvider(signer)
        pk = provider.public_key_b64
        assert len(pk) > 10
        assert pk == signer.public_key_b64


# --- payments/mock_license_facilitator.py:90-91 — _extract_domain exception ---

class TestExtractDomain:
    def test_extract_domain_valid(self):
        """Covers mock_license_facilitator.py:86-89 — normal URL parsing."""
        assert _extract_domain("https://example.com/path") == "example.com"

    def test_extract_domain_invalid(self):
        """Covers mock_license_facilitator.py:90-91 — exception returns empty string."""
        assert _extract_domain("") == ""


# --- payments/facilitator.py:7-16 — re-export module ---

class TestFacilitatorReExports:
    def test_import_from_payments_facilitator(self):
        """Covers payments/facilitator.py:7-16 — backward compat re-exports."""
        from payments.facilitator import (
            BaseFacilitator,
            Facilitator,
            FacilitatorResult,
            PaymentNetwork,
            PaymentRequirement,
        )
        assert Facilitator is BaseFacilitator
        assert PaymentNetwork.BASE.value == "base"


# --- api/routes.py:233-239 — /compliance/optout endpoint ---

class TestComplianceOptoutEndpoint:
    async def test_optout_check(self, client: AsyncClient):
        """Covers routes.py:233-239 — /compliance/optout endpoint."""
        resp = await client.get("/compliance/optout", params={"domain": "example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["domain"] == "example.com"
        assert "opted_out" in data
        assert "entries" in data


# --- api/routes.py:56 — enable_preferred_access disabled ---

class TestPreferredAccessDisabled:
    async def test_no_steering_when_disabled(self):
        """Covers routes.py:56 — early return when enable_preferred_access is False."""
        mock_llm = AsyncMock()
        mock_llm.choices = [AsyncMock(message=AsyncMock(content="Summary."))]
        mock_llm.model = "test"
        mock_llm.usage = AsyncMock(total_tokens=10)

        mock_conversion = ConversionResult(
            markdown="# Test", title="Test", author=None, date=None, url="https://example.com",
        )

        import os
        old_val = os.environ.get("FAIRFETCH_PREFERRED_ACCESS")
        os.environ["FAIRFETCH_PREFERRED_ACCESS"] = "false"

        try:
            from api.dependencies import get_config
            get_config.cache_clear()

            from api.main import create_app
            from httpx import ASGITransport, AsyncClient as AC

            with (
                patch("core.summarizer.litellm.acompletion", return_value=mock_llm),
                patch("core.converter.ContentConverter.from_url", new_callable=AsyncMock, return_value=mock_conversion),
            ):
                app = create_app()
                transport = ASGITransport(app=app)
                async with AC(transport=transport, base_url="http://test") as ac:
                    resp = await ac.get(
                        "/content/fetch",
                        params={"url": "https://example.com"},
                        headers={
                            "X-PAYMENT": "test_paid_fairfetch",
                            "User-Agent": "GPTBot/1.0",
                            "Accept": "text/html",
                        },
                    )
                    assert resp.headers.get("X-FairFetch-Preferred-Access") is None
        finally:
            if old_val is None:
                os.environ.pop("FAIRFETCH_PREFERRED_ACCESS", None)
            else:
                os.environ["FAIRFETCH_PREFERRED_ACCESS"] = old_val
            get_config.cache_clear()


# --- api/routes.py:85 — _issue_grant_for_response with no license_provider ---

class TestNoLicenseProvider:
    async def test_no_grant_when_provider_missing(self):
        """Covers routes.py:84-85 — returns empty string when no license_provider."""
        mock_llm = AsyncMock()
        mock_llm.choices = [AsyncMock(message=AsyncMock(content="Summary."))]
        mock_llm.model = "test"
        mock_llm.usage = AsyncMock(total_tokens=10)

        mock_conversion = ConversionResult(
            markdown="# Test", title="Test", author=None, date=None, url="https://example.com",
        )

        import os
        old_val = os.environ.get("FAIRFETCH_ENABLE_GRANTS")
        os.environ["FAIRFETCH_ENABLE_GRANTS"] = "false"

        try:
            from api.dependencies import get_config
            get_config.cache_clear()

            from api.main import create_app
            from httpx import ASGITransport, AsyncClient as AC

            with (
                patch("core.summarizer.litellm.acompletion", return_value=mock_llm),
                patch("core.converter.ContentConverter.from_url", new_callable=AsyncMock, return_value=mock_conversion),
            ):
                app = create_app()
                transport = ASGITransport(app=app)
                async with AC(transport=transport, base_url="http://test") as ac:
                    resp = await ac.get(
                        "/content/fetch",
                        params={"url": "https://example.com"},
                        headers={"X-PAYMENT": "test_paid_fairfetch"},
                    )
                    assert resp.status_code == 200
                    assert resp.headers.get("X-FairFetch-License-ID", "") == ""
        finally:
            if old_val is None:
                os.environ.pop("FAIRFETCH_ENABLE_GRANTS", None)
            else:
                os.environ["FAIRFETCH_ENABLE_GRANTS"] = old_val
            get_config.cache_clear()


# --- core/converter.py:73-74,79 — XML parse error and markdownify fallback ---

class TestConverterFallbacks:
    async def test_markdownify_fallback_when_trafilatura_returns_none(self):
        """Covers converter.py:79 — markdownify used when trafilatura returns None."""
        html = "<html><body><p>Simple paragraph.</p></body></html>"
        converter = ContentConverter()

        with patch("core.converter.trafilatura.extract", return_value=None):
            result = await converter.from_html(html, url="https://example.com")
            assert len(result.markdown) > 0

    async def test_xml_parse_error_handled(self):
        """Covers converter.py:73-74 — ET.ParseError caught gracefully."""
        html = "<html><body><p>Content here.</p></body></html>"
        converter = ContentConverter()

        def mock_extract(html, **kwargs):
            if kwargs.get("output_format") == "xml":
                return "<<<invalid xml>>>"
            return "Extracted content"

        with patch("core.converter.trafilatura.extract", side_effect=mock_extract):
            result = await converter.from_html(html, url="https://example.com")
            assert result.title is None
            assert result.markdown == "Extracted content"


# --- mcp_server/server.py:183,196 — MCP resource functions ---

class TestMCPResources:
    async def test_get_config_resource(self):
        """Covers server.py:183 — fairfetch://config resource."""
        import json
        from mcp_server.server import get_config
        result = await get_config()
        data = json.loads(result)
        assert data["version"] == "0.2.0"
        assert "public_key" in data
        assert "pillars" in data
        assert "green-ai" in data["pillars"]

    async def test_get_public_key_resource(self):
        """Covers server.py:196 — fairfetch://public-key resource."""
        from mcp_server.server import get_public_key
        key = await get_public_key()
        assert len(key) > 10


# --- api/routes.py:98-99 — _issue_grant_for_response exception path ---

class TestGrantIssuanceException:
    async def test_grant_exception_returns_empty(self):
        """Covers routes.py:98-99 — exception in grant issuance returns empty string."""
        mock_llm = AsyncMock()
        mock_llm.choices = [AsyncMock(message=AsyncMock(content="Summary."))]
        mock_llm.model = "test"
        mock_llm.usage = AsyncMock(total_tokens=10)

        mock_conversion = ConversionResult(
            markdown="# Test", title="Test", author=None, date=None, url="https://example.com",
        )

        with (
            patch("core.summarizer.litellm.acompletion", return_value=mock_llm),
            patch("core.converter.ContentConverter.from_url", new_callable=AsyncMock, return_value=mock_conversion),
        ):
            from api.main import create_app
            from httpx import ASGITransport, AsyncClient as AC

            app = create_app()
            app.state.license_provider.issue_grant = AsyncMock(side_effect=RuntimeError("boom"))

            transport = ASGITransport(app=app)
            async with AC(transport=transport, base_url="http://test") as ac:
                resp = await ac.get(
                    "/content/fetch",
                    params={"url": "https://example.com"},
                    headers={"X-PAYMENT": "test_paid_fairfetch"},
                )
                assert resp.status_code == 200


# --- payments/x402.py:99-100 — middleware grant issuance exception path ---

class TestX402GrantException:
    async def test_middleware_grant_exception_logged(self):
        """Covers x402.py:99-100 — exception during middleware grant issuance."""
        mock_llm = AsyncMock()
        mock_llm.choices = [AsyncMock(message=AsyncMock(content="Summary."))]
        mock_llm.model = "test"
        mock_llm.usage = AsyncMock(total_tokens=10)

        mock_conversion = ConversionResult(
            markdown="# Test", title="Test", author=None, date=None, url="https://example.com",
        )

        failing_provider = AsyncMock()
        failing_provider.issue_grant = AsyncMock(side_effect=RuntimeError("grant failure"))

        with (
            patch("core.summarizer.litellm.acompletion", return_value=mock_llm),
            patch("core.converter.ContentConverter.from_url", new_callable=AsyncMock, return_value=mock_conversion),
        ):
            from api.main import create_app
            from httpx import ASGITransport, AsyncClient as AC

            app = create_app()
            for mw in app.user_middleware:
                if hasattr(mw, 'kwargs') and 'license_provider' in mw.kwargs:
                    mw.kwargs['license_provider'] = failing_provider

            transport = ASGITransport(app=app)
            async with AC(transport=transport, base_url="http://test") as ac:
                resp = await ac.get(
                    "/content/fetch",
                    params={"url": "https://example.com"},
                    headers={"X-PAYMENT": "test_paid_fairfetch"},
                )
                assert resp.status_code == 200


# --- api/dependencies.py:78,84,90 — non-test-mode branches + unused builder ---

class TestDependencyBuilders:
    def test_build_facilitator_non_test_mode(self):
        """Covers dependencies.py:78 — else branch."""
        from api.dependencies import FairFetchConfig, build_facilitator
        config = FairFetchConfig(test_mode=False)
        f = build_facilitator(config)
        assert f is not None

    def test_build_license_provider_non_test_mode(self):
        """Covers dependencies.py:84 — else branch."""
        from api.dependencies import FairFetchConfig, build_license_provider
        config = FairFetchConfig(test_mode=False)
        signer = Ed25519Signer()
        lp = build_license_provider(config, signer)
        assert lp is not None

    def test_build_license_facilitator(self):
        """Covers dependencies.py:90 — unused builder function."""
        from api.dependencies import FairFetchConfig, build_license_facilitator
        config = FairFetchConfig()
        signer = Ed25519Signer()
        lf = build_license_facilitator(config, signer)
        assert lf is not None
