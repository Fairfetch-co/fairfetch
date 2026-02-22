"""BaseFacilitator — abstract interface for x402 payment verification and settlement.

Part of the FairFetch Open Standard. Implementations include:
  - MockFacilitator (local dev, no wallet required)
  - CloudFacilitator (FairFetch Managed Clearinghouse, via plugins/)
  - Self-hosted EIP-3009 verifier
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, Field


class PaymentNetwork(str, Enum):
    BASE = "base"
    ETHEREUM = "ethereum"
    POLYGON = "polygon"


class PaymentRequirement(BaseModel):
    """Describes what payment the publisher requires (returned in 402 body)."""

    price: str = Field(description="Amount in smallest unit (e.g. '1000' for $0.001 USDC)")
    asset: str = Field(default="USDC", description="Payment asset symbol")
    network: PaymentNetwork = Field(default=PaymentNetwork.BASE)
    pay_to: str = Field(description="Publisher wallet address (EVM)")
    facilitator_url: str = Field(
        default="https://x402.org/facilitator",
        description="URL of the facilitator service",
    )
    description: str = Field(default="Content access fee")
    extra: dict[str, str] = Field(default_factory=dict)

    def to_402_body(self) -> dict:
        return {
            "accepts": {
                "price": self.price,
                "asset": self.asset,
                "network": self.network.value,
                "payTo": self.pay_to,
                "facilitator": self.facilitator_url,
                "description": self.description,
                **self.extra,
            },
            "error": "Payment Required",
            "message": (
                "This content requires micro-payment. Include an X-PAYMENT header "
                "with a valid payment proof. See https://fairfetch.dev/docs/x402"
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
    async def verify(self, payment_header: str, requirement: PaymentRequirement) -> FacilitatorResult:
        """Verify a payment proof against the requirement. Does not settle."""
        ...

    @abstractmethod
    async def settle(self, payment_header: str, requirement: PaymentRequirement) -> FacilitatorResult:
        """Verify and settle (finalize) the payment on-chain."""
        ...
