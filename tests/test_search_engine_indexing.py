"""Tests for search engine indexing usage category and allow/block list."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.dependencies import _parse_list_env
from api.main import create_app
from core.search_engine import is_allowed_search_engine
from interfaces.license_provider import (
    USAGE_CATEGORY_META,
    UsageCategory,
    get_price_multiplier,
)
from tests.conftest import MOCK_CONVERSION


class TestSearchEngineIndexingCategory:
    def test_category_exists_and_is_free(self):
        assert hasattr(UsageCategory, "SEARCH_ENGINE_INDEXING")
        assert UsageCategory.SEARCH_ENGINE_INDEXING.value == "search_engine_indexing"
        assert get_price_multiplier(UsageCategory.SEARCH_ENGINE_INDEXING) == 0
        meta = USAGE_CATEGORY_META[UsageCategory.SEARCH_ENGINE_INDEXING]
        assert meta["price_multiplier"] == 0
        assert "indexing" in str(meta["description"]).lower()


class TestParseListEnv:
    def test_empty_or_unset_returns_default(self):
        result = _parse_list_env("FAIRFETCH_NONEXISTENT_KEY_XYZ", ("a", "b"))
        assert result == ["a", "b"]
        result = _parse_list_env("FAIRFETCH_SEARCH_ENGINES_BLOCKED", ())
        assert result == []

    def test_comma_separated_parsed(self):
        import os

        with patch.dict(os.environ, {"FAIRFETCH_SEARCH_ENGINES_ALLOWED": "Googlebot,Bingbot"}):
            result = _parse_list_env("FAIRFETCH_SEARCH_ENGINES_ALLOWED", ())
            assert result == ["Googlebot", "Bingbot"]


class TestIsAllowedSearchEngine:
    def test_allowed_match(self):
        assert (
            is_allowed_search_engine(
                "Mozilla/5.0 (compatible; Googlebot/2.1)",
                ["Googlebot"],
                [],
            )
            is True
        )
        assert (
            is_allowed_search_engine(
                "DuckDuckBot/1.0",
                ["DuckDuckBot", "Bingbot"],
                [],
            )
            is True
        )

    def test_blocked_takes_precedence(self):
        assert (
            is_allowed_search_engine(
                "Googlebot/2.1",
                ["Googlebot"],
                ["Googlebot"],
            )
            is False
        )
        assert (
            is_allowed_search_engine(
                "Mozilla/5.0 Googlebot/2.1",
                ["Googlebot"],
                ["Googlebot"],
            )
            is False
        )

    def test_no_match_returns_false(self):
        assert (
            is_allowed_search_engine(
                "curl/7.68.0",
                ["Googlebot", "Bingbot"],
                [],
            )
            is False
        )
        assert is_allowed_search_engine("", ["Googlebot"], []) is False

    def test_case_insensitive(self):
        assert (
            is_allowed_search_engine(
                "googlebot/2.1",
                ["Googlebot"],
                [],
            )
            is True
        )


@pytest.fixture
async def client():
    with (
        patch("core.summarizer.litellm.acompletion", return_value=AsyncMock()),
        patch(
            "core.converter.ContentConverter.from_url",
            new_callable=AsyncMock,
            return_value=MOCK_CONVERSION,
        ),
    ):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.mark.asyncio
async def test_allowed_search_engine_gets_free_access(client: AsyncClient):
    """Allowed search engine with usage=search_engine_indexing gets 200 and free."""
    resp = await client.get(
        "/content/fetch",
        params={"url": "https://example.com", "usage": "search_engine_indexing"},
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Accept": "text/markdown",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-FairFetch-Payment-Method") == "free"
    assert resp.headers.get("X-PAYMENT-RECEIPT") == "free"


@pytest.mark.asyncio
async def test_non_allowed_search_engine_indexing_gets_402(client: AsyncClient):
    """Non-allowed crawler with usage=search_engine_indexing gets 402 with base price."""
    resp = await client.get(
        "/content/fetch",
        params={"url": "https://example.com", "usage": "search_engine_indexing"},
        headers={"User-Agent": "curl/7.68.0"},
    )
    assert resp.status_code == 402
    data = resp.json()
    assert "accepts" in data
    assert data["accepts"]["usage_category"] == "search_engine_indexing"
    assert int(data["accepts"]["price"]) == 1000
    assert "search_engine_indexing" in data.get("available_tiers", {})
