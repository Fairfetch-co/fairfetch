"""Tests for route-based (variable) pricing."""

from __future__ import annotations

from api.dependencies import (
    FairFetchConfig,
    _parse_price_by_route,
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
