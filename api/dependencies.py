"""FairFetchConfig and dependency injection — single source of truth for all runtime config."""

from __future__ import annotations

import os
from functools import lru_cache

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


class FairFetchConfig(BaseModel):
    """Centralized runtime configuration — loaded entirely from env vars.

    Replaces all hardcoded values. Every tunable in the system is here.
    """

    test_mode: bool = Field(default=True)
    publisher_wallet: str = Field(default="0x0000000000000000000000000000000000000000")
    publisher_domain: str = Field(default="localhost")
    content_price: str = Field(default="1000")
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

    @classmethod
    def from_env(cls) -> FairFetchConfig:
        return cls(
            test_mode=os.getenv("FAIRFETCH_TEST_MODE", "true").lower() == "true",
            publisher_wallet=os.getenv(
                "FAIRFETCH_PUBLISHER_WALLET", "0x0000000000000000000000000000000000000000"
            ),
            publisher_domain=os.getenv("FAIRFETCH_PUBLISHER_DOMAIN", "localhost"),
            content_price=os.getenv("FAIRFETCH_CONTENT_PRICE", "1000"),
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


def build_payment_requirement(config: FairFetchConfig) -> PaymentRequirement:
    return PaymentRequirement(
        price=config.content_price,
        pay_to=config.publisher_wallet,
        facilitator_url=config.facilitator_url,
    )


def build_converter() -> ContentConverter:
    return ContentConverter()


def build_summarizer(config: FairFetchConfig) -> BaseSummarizer:
    return Summarizer(model=config.litellm_model)


def build_packet_builder(signer: Ed25519Signer) -> KnowledgePacketBuilder:
    return KnowledgePacketBuilder(signer=signer)
