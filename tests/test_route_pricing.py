"""Tests for route-based (variable) pricing."""

from __future__ import annotations

from api.dependencies import (
    FairFetchConfig,
    _parse_price_by_route,
    _path_from_content_url,
    build_payment_requirement,
    resolve_content_price,
)


class TestParsePriceByRoute:
    def test_empty_or_blank_returns_empty_dict(self):
        assert _parse_price_by_route("") == {}
        assert _parse_price_by_route("   ") == {}

    def test_valid_json_parsed(self):
        assert _parse_price_by_route('{"": "1000", "/business": "2000"}') == {
            "": "1000",
            "/business": "2000",
        }
        assert _parse_price_by_route('{"/sports": "500", "/business": "2000"}') == {
            "/sports": "500",
            "/business": "2000",
        }

    def test_invalid_json_returns_empty_dict(self):
        assert _parse_price_by_route("not json") == {}
        assert _parse_price_by_route("{/business: 2000}") == {}

    def test_non_numeric_prices_dropped(self):
        # Only numeric price strings are kept; invalid values skipped
        result = _parse_price_by_route(
            '{"": "1000", "/a": "2000", "/b": "bad", "/c": "3.14", "/d": ""}'
        )
        assert result == {"": "1000", "/a": "2000"}

    def test_max_entries_cap(self):
        # More than _MAX_PRICE_BY_ROUTE_ENTRIES: only first 256 kept
        from api.dependencies import _MAX_PRICE_BY_ROUTE_ENTRIES

        entries = {f"/p{i}": "1000" for i in range(_MAX_PRICE_BY_ROUTE_ENTRIES + 10)}
        raw = "{" + ", ".join(f'"{k}": "{v}"' for k, v in entries.items()) + "}"
        result = _parse_price_by_route(raw)
        assert len(result) == _MAX_PRICE_BY_ROUTE_ENTRIES


class TestResolveContentPrice:
    def test_no_rules_uses_default(self):
        config = FairFetchConfig(content_price="1000", price_by_route={})
        assert resolve_content_price(config, "https://example.com/any/path") == "1000"

    def test_longest_prefix_wins(self):
        config = FairFetchConfig(
            content_price="1000",
            price_by_route={
                "": "500",
                "/business": "2000",
                "/business/breaking": "3000",
            },
        )
        assert resolve_content_price(config, "https://abc.com/business") == "2000"
        assert resolve_content_price(config, "https://abc.com/business/breaking") == "3000"
        assert resolve_content_price(config, "https://abc.com/business/other") == "2000"
        assert resolve_content_price(config, "https://abc.com/sports") == "500"

    def test_explicit_default_key(self):
        config = FairFetchConfig(
            content_price="1000",
            price_by_route={"": "999", "/premium": "5000"},
        )
        assert resolve_content_price(config, "https://x.com/other") == "999"
        assert resolve_content_price(config, "https://x.com/premium") == "5000"

    def test_bare_path_handled(self):
        config = FairFetchConfig(
            content_price="1000",
            price_by_route={"/business": "2000"},
        )
        assert resolve_content_price(config, "/business") == "2000"
        assert resolve_content_price(config, "/sports") == "1000"

    def test_path_normalization_prevents_bypass(self):
        # Traversal: /business/../sports must resolve to /sports price
        config = FairFetchConfig(
            content_price="1000",
            price_by_route={"/business": "2000", "/sports": "500"},
        )
        assert resolve_content_price(config, "https://x.com/business/../sports") == "500"
        assert resolve_content_price(config, "https://x.com/sports/../sports") == "500"

    def test_percent_encoded_path_normalized(self):
        # %2F (encoded /) decoded so path matches consistently
        config = FairFetchConfig(
            content_price="1000",
            price_by_route={"/business": "2000"},
        )
        assert resolve_content_price(config, "https://x.com/business") == "2000"
        # Path with encoded slash still matches after unquote
        assert resolve_content_price(config, "https://x.com%2Fbusiness") == "2000"

    def test_invalid_content_price_fallback(self):
        config = FairFetchConfig(
            content_price="not_a_number",
            price_by_route={},
        )
        assert resolve_content_price(config, "https://x.com/any") == "1000"

    def test_invalid_route_price_fallback_to_default(self):
        config = FairFetchConfig(
            content_price="1000",
            price_by_route={"/premium": "invalid", "": "999"},
        )
        # /premium matches but value invalid -> fall through to "" -> 999
        assert resolve_content_price(config, "https://x.com/premium") == "999"


class TestBuildPaymentRequirementWithRoute:
    def test_without_content_url_uses_default_price(self):
        config = FairFetchConfig(content_price="1000")
        req = build_payment_requirement(config)
        assert req.price == "1000"

    def test_with_content_url_uses_route_price(self):
        config = FairFetchConfig(
            content_price="1000",
            price_by_route={"/business": "2000", "/sports": "500"},
        )
        req_business = build_payment_requirement(config, "https://abc.com/business")
        req_sports = build_payment_requirement(config, "https://abc.com/sports")
        assert req_business.price == "2000"
        assert req_sports.price == "500"


class TestPathNormalization:
    """Security: path normalization to prevent price bypass."""

    def test_traversal_collapsed(self):
        assert _path_from_content_url("https://x.com/business/../sports") == "/sports"
        assert _path_from_content_url("https://x.com/a/b/../../c") == "/c"

    def test_dot_segments_removed(self):
        assert _path_from_content_url("https://x.com/./business/.//x") == "/business/x"

    def test_path_length_capped(self):
        from api.dependencies import _MAX_PATH_LENGTH

        long_path = "https://x.com/" + ("a" * (_MAX_PATH_LENGTH + 100))
        result = _path_from_content_url(long_path)
        assert len(result) <= _MAX_PATH_LENGTH + 1  # +1 for leading /
