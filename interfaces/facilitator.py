"""BaseFacilitator — abstract interface for x402 payment verification and settlement.

Part of the FairFetch Open Standard. Implementations include:
  - MockFacilitator (local dev, no wallet required)
  - CloudFacilitator (FairFetch Managed Clearinghouse, via plugins/)
  - Self-hosted EIP-3009 verifier
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from pydantic import BaseModel, Field

from interfaces.license_provider import (
    USAGE_CATEGORY_META,
    UsageCategory,
    get_price_multiplier,
)


class PaymentNetwork(StrEnum):
    BASE = "base"
    ETHEREUM = "ethereum"
    POLYGON = "polygon"


class PaymentRequirement(BaseModel):
    """Describes what payment the publisher requires (returned in 402 body).

    Pricing is usage-category-aware: the base price is multiplied by the
    category's tier multiplier (e.g. 1x for summary, 5x for training).
    """

    price: str = Field(description="Base price in smallest unit (e.g. '1000' for $0.001 USDC)")
    asset: str = Field(default="USDC", description="Payment asset symbol")
    network: PaymentNetwork = Field(default=PaymentNetwork.BASE)
    pay_to: str = Field(description="Publisher wallet address (EVM)")
    facilitator_url: str = Field(
        default="https://x402.org/facilitator",
        description="URL of the facilitator service",
    )
    description: str = Field(default="Content access fee")
    usage_category: str = Field(
        default=UsageCategory.SUMMARY,
        description="Intended usage: search_engine_indexing, summary, rag, research, training, commercial",  # noqa: E501
    )
    extra: dict[str, str] = Field(default_factory=dict)

    def effective_price(self) -> str:
        """Base price * usage-category multiplier."""
        try:
            category = UsageCategory(self.usage_category)
            multiplier = get_price_multiplier(category)
        except ValueError:
            multiplier = 1
        return str(int(self.price) * multiplier)

    def to_402_body(self) -> dict[str, object]:
        try:
            category = UsageCategory(self.usage_category)
            meta = USAGE_CATEGORY_META[category]
        except (ValueError, KeyError):
            meta = {}

        available_tiers: dict[str, object] = {}
        for cat in UsageCategory:
            cat_meta = USAGE_CATEGORY_META[cat]
            multiplier = get_price_multiplier(cat)
            available_tiers[cat.value] = {
                "price": str(int(self.price) * multiplier),
                "compliance_level": str(cat_meta["compliance_level"]),
                "description": str(cat_meta["description"]),
            }

        return {
            "accepts": {
                "price": self.effective_price(),
                "asset": self.asset,
                "network": self.network.value,
                "payTo": self.pay_to,
                "facilitator": self.facilitator_url,
                "description": self.description,
                "usage_category": self.usage_category,
                "compliance_level": str(meta.get("compliance_level", "standard")),
                **self.extra,
            },
            "available_tiers": available_tiers,
            "error": "Payment Required",
            "message": (
                "This content requires micro-payment. Include an X-PAYMENT header "
                "with a valid payment proof. Specify usage via X-USAGE-CATEGORY. "
                "See https://fairfetch.dev/docs/x402"
            ),
        }


class FacilitatorResult(BaseModel):
    """Result from the facilitator's verify/settle endpoints."""

    valid: bool
    tx_hash: str = ""
    error: str = ""
    payer: str = ""
    amount: str = ""


class BaseFacilitator(ABC):
    """Abstract base for payment facilitators (production or mock)."""

    @abstractmethod
    async def verify(
        self, payment_header: str, requirement: PaymentRequirement
    ) -> FacilitatorResult:
        """Verify a payment proof against the requirement. Does not settle."""
        ...

    @abstractmethod
    async def settle(
        self, payment_header: str, requirement: PaymentRequirement
    ) -> FacilitatorResult:
        """Verify and settle (finalize) the payment on-chain."""
        ...
