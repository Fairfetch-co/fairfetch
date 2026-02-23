"""FairFetchConfig and dependency injection — single source of truth for all runtime config."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from urllib.parse import unquote, urlparse

from pydantic import BaseModel, Field

from core.converter import ContentConverter
from core.knowledge_packet import KnowledgePacketBuilder
from core.signatures import Ed25519Signer
from core.summarizer import Summarizer
from interfaces.facilitator import BaseFacilitator, PaymentRequirement
from interfaces.license_provider import BaseLicenseProvider, UsageCategory
from interfaces.summarizer import BaseSummarizer
from payments.mock_facilitator import MockFacilitator
from payments.mock_license_facilitator import MockLicenseFacilitator, MockLicenseProvider

# Default User-Agent substrings for search engines allowed free indexing (site owner can override)
_DEFAULT_SEARCH_ENGINES_ALLOWED = (
    "Googlebot",
    "Bingbot",
    "DuckDuckBot",
    "Slurp",  # Yahoo
    "Baiduspider",
    "YandexBot",
    "Sogou",
    "Exabot",
    "facebookexternalhit",
    "ia_archiver",  # Alexa
)


class FairFetchConfig(BaseModel):
    """Centralized runtime configuration — loaded entirely from env vars.

    Replaces all hardcoded values. Every tunable in the system is here.
    """

    test_mode: bool = Field(default=True)
    publisher_wallet: str = Field(default="0x0000000000000000000000000000000000000000")
    publisher_domain: str = Field(default="localhost")
    content_price: str = Field(default="1000")
    """Default base price (smallest unit). Overridden by price_by_route when set."""
    price_by_route: dict[str, str] = Field(default_factory=dict)
    """Path prefix -> base price. Longest match wins. E.g. /business, /sports."""
    facilitator_url: str = Field(default="https://x402.org/facilitator")
    litellm_model: str = Field(default="gpt-4o-mini")
    signing_key: str = Field(default="")
    license_type: str = Field(default="publisher-terms")
    default_usage_category: str = Field(default=UsageCategory.SUMMARY)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8402)

    llms_txt_url: str = Field(default="/.well-known/llms.txt")
    mcp_endpoint: str = Field(default="/mcp")

    enable_usage_grants: bool = Field(default=True)
    enable_preferred_access: bool = Field(default=True)

    search_engines_allowed: list[str] = Field(
        default_factory=lambda: list(_DEFAULT_SEARCH_ENGINES_ALLOWED),
        description="User-Agent substrings for search engines allowed free indexing",
    )
    search_engines_blocked: list[str] = Field(
        default_factory=list,
        description="User-Agent substrings for search engines never given free indexing",
    )

    @classmethod
    def from_env(cls) -> FairFetchConfig:
        return cls(
            test_mode=os.getenv("FAIRFETCH_TEST_MODE", "true").lower() == "true",
            publisher_wallet=os.getenv(
                "FAIRFETCH_PUBLISHER_WALLET", "0x0000000000000000000000000000000000000000"
            ),
            publisher_domain=os.getenv("FAIRFETCH_PUBLISHER_DOMAIN", "localhost"),
            content_price=os.getenv("FAIRFETCH_CONTENT_PRICE", "1000"),
            price_by_route=_parse_price_by_route(os.getenv("FAIRFETCH_PRICE_BY_ROUTE", "")),
            facilitator_url=os.getenv("FAIRFETCH_FACILITATOR_URL", "https://x402.org/facilitator"),
            litellm_model=os.getenv("LITELLM_MODEL", "gpt-4o-mini"),
            signing_key=os.getenv("FAIRFETCH_SIGNING_KEY", ""),
            license_type=os.getenv("FAIRFETCH_LICENSE_TYPE", "publisher-terms"),
            default_usage_category=os.getenv(
                "FAIRFETCH_DEFAULT_USAGE_CATEGORY", UsageCategory.SUMMARY
            ),
            host=os.getenv("FAIRFETCH_HOST", "0.0.0.0"),
            port=int(os.getenv("FAIRFETCH_PORT", "8402")),
            llms_txt_url=os.getenv("FAIRFETCH_LLMS_TXT_URL", "/.well-known/llms.txt"),
            mcp_endpoint=os.getenv("FAIRFETCH_MCP_ENDPOINT", "/mcp"),
            enable_usage_grants=os.getenv("FAIRFETCH_ENABLE_GRANTS", "true").lower() == "true",
            enable_preferred_access=(
                os.getenv("FAIRFETCH_PREFERRED_ACCESS", "true").lower() == "true"
            ),
            search_engines_allowed=_parse_list_env(
                "FAIRFETCH_SEARCH_ENGINES_ALLOWED", _DEFAULT_SEARCH_ENGINES_ALLOWED
            ),
            search_engines_blocked=_parse_list_env("FAIRFETCH_SEARCH_ENGINES_BLOCKED", ()),
        )


@lru_cache
def get_config() -> FairFetchConfig:
    return FairFetchConfig.from_env()


def build_signer(config: FairFetchConfig) -> Ed25519Signer:
    return Ed25519Signer(config.signing_key or None)


def build_facilitator(config: FairFetchConfig) -> BaseFacilitator:
    if config.test_mode:
        return MockFacilitator()
    return MockFacilitator()


def build_license_provider(config: FairFetchConfig, signer: Ed25519Signer) -> BaseLicenseProvider:
    if config.test_mode:
        return MockLicenseProvider(signer)
    return MockLicenseProvider(signer)


def build_license_facilitator(
    config: FairFetchConfig, signer: Ed25519Signer
) -> MockLicenseFacilitator:
    return MockLicenseFacilitator(signer)


# Max path length for route matching to avoid DoS from huge URLs
_MAX_PATH_LENGTH = 2048
# Max route rules to avoid DoS from huge FAIRFETCH_PRICE_BY_ROUTE
_MAX_PRICE_BY_ROUTE_ENTRIES = 256


def _is_valid_price_string(s: str) -> bool:
    """True if s is a non-empty string of digits (safe for int())."""
    return isinstance(s, str) and len(s) <= 20 and s.isdigit()


def _parse_list_env(
    key: str,
    default: tuple[str, ...] | list[str],
) -> list[str]:
    """Parse comma-separated env var into list of stripped strings; use default if unset."""
    raw = os.getenv(key, "").strip()
    if not raw:
        return list(default)
    return [s.strip() for s in raw.split(",") if s.strip()]


def _parse_price_by_route(raw: str) -> dict[str, str]:
    """Parse FAIRFETCH_PRICE_BY_ROUTE JSON (path prefix -> price). Only numeric prices kept."""
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        out: dict[str, str] = {}
        for k, v in data.items():
            if len(out) >= _MAX_PRICE_BY_ROUTE_ENTRIES:
                break
            vs = str(v)
            if _is_valid_price_string(vs):
                out[str(k)] = vs
        return out
    except (json.JSONDecodeError, TypeError):
        return {}


def resolve_content_price(config: FairFetchConfig, content_url: str) -> str:
    """Resolve base price for a content URL using path-based route rules.

    The content URL path (e.g. /business, /sports) is matched against
    config.price_by_route; longest matching prefix wins. If no rules or no
    match, returns config.content_price. Path is normalized to prevent
    bypass via encoding or traversal.
    """
    if not config.price_by_route:
        return config.content_price if _is_valid_price_string(config.content_price) else "1000"
    path = _path_from_content_url(content_url)
    # Longest matching prefix first
    candidates = sorted(config.price_by_route.keys(), key=len, reverse=True)
    for prefix in candidates:
        if path == prefix or path.startswith(prefix + "/"):
            price = config.price_by_route[prefix]
            if _is_valid_price_string(price):
                return price
            break
    # Explicit default key "" if present
    if "" in config.price_by_route:
        p = config.price_by_route[""]
        if _is_valid_price_string(p):
            return p
    # Fallback: ensure we never return a non-numeric price (misconfig)
    return config.content_price if _is_valid_price_string(config.content_price) else "1000"


def _normalize_path(path: str) -> str:
    """Decode percent-encoding and collapse . / .. segments to prevent price bypass."""
    decoded = unquote(path)
    if len(decoded) > _MAX_PATH_LENGTH:
        decoded = decoded[:_MAX_PATH_LENGTH]
    parts = decoded.split("/")
    out: list[str] = []
    for part in parts:
        if part == ".":
            continue
        if part == "":
            if not out:
                out.append("")
            continue
        if part == "..":
            if out and out[-1] != "":
                out.pop()
            continue
        out.append(part)
    joined = "/".join(out) if out else "/"
    return joined if joined.startswith("/") else "/" + joined


def _path_from_content_url(content_url: str) -> str:
    """Extract and normalize path for route matching. Handles full URLs and bare paths.
    Decodes percent-encoding before parsing so %2F cannot be used to bypass route match.
    """
    s = (content_url or "").strip()
    if not s:
        return "/"
    if "://" in s:
        # Decode so path is consistent (e.g. %2F -> /) and cannot be used to bypass
        s = unquote(s)
        parsed = urlparse(s)
        path = parsed.path or "/"
    else:
        path = s if s.startswith("/") else "/" + s
    path = path or "/"
    return _normalize_path(path)


def build_payment_requirement(
    config: FairFetchConfig,
    content_url: str | None = None,
) -> PaymentRequirement:
    """Build payment requirement; if content_url is set, use route-based price when configured."""
    price = (
        resolve_content_price(config, content_url or "") if content_url else config.content_price
    )
    return PaymentRequirement(
        price=price,
        pay_to=config.publisher_wallet,
        facilitator_url=config.facilitator_url,
    )


def build_converter() -> ContentConverter:
    return ContentConverter()


def build_summarizer(config: FairFetchConfig) -> BaseSummarizer:
    return Summarizer(model=config.litellm_model)


def build_packet_builder(signer: Ed25519Signer) -> KnowledgePacketBuilder:
    return KnowledgePacketBuilder(signer=signer)
