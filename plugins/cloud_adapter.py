"""Cloud Adapter placeholder — connects to the FairFetch Managed Clearinghouse.

This module demonstrates how to implement BaseFacilitator and BaseLicenseProvider
for the FairFetch cloud service. In the open-source version, only the Mock
implementations are provided. The managed cloud service handles:

  - Real EIP-3009 (gasless USDC) payment verification and settlement
  - Publisher-verified Ed25519 key management
  - Usage Grant persistence and audit trail
  - Revenue distribution to publishers

To use the managed service:
  1. Sign up at https://clearinghouse.fairfetch.dev
  2. Get your API key and publisher ID
  3. Set FAIRFETCH_CLOUD_API_KEY and FAIRFETCH_PUBLISHER_ID env vars
  4. Set FAIRFETCH_TEST_MODE=false

Example:
    from plugins.cloud_adapter import CloudFacilitator, CloudLicenseProvider

    facilitator = CloudFacilitator(api_key="...", publisher_id="...")
    license_provider = CloudLicenseProvider(api_key="...", publisher_id="...")
"""

from __future__ import annotations

import os

import httpx

from interfaces.facilitator import BaseFacilitator, FacilitatorResult, PaymentRequirement
from interfaces.license_provider import BaseLicenseProvider, UsageGrant


class CloudFacilitator(BaseFacilitator):
    """Production facilitator that calls the FairFetch Managed Clearinghouse.

    Handles real on-chain settlement via EIP-3009 (gasless USDC).
    This is a placeholder — the actual implementation is part of the
    FairFetch commercial cloud offering.
    """

    def __init__(
        self,
        *,
        api_key: str = "",
        publisher_id: str = "",
        base_url: str = "https://clearinghouse.fairfetch.dev/api/v1",
    ) -> None:
        self._api_key = api_key or os.getenv("FAIRFETCH_CLOUD_API_KEY", "")
        self._publisher_id = publisher_id or os.getenv("FAIRFETCH_PUBLISHER_ID", "")
        self._base_url = base_url

    async def verify(self, payment_header: str, requirement: PaymentRequirement) -> FacilitatorResult:
        raise NotImplementedError(
            "CloudFacilitator requires a FairFetch Cloud subscription. "
            "See https://clearinghouse.fairfetch.dev for details. "
            "Use MockFacilitator for local development."
        )

    async def settle(self, payment_header: str, requirement: PaymentRequirement) -> FacilitatorResult:
        raise NotImplementedError(
            "CloudFacilitator requires a FairFetch Cloud subscription. "
            "See https://clearinghouse.fairfetch.dev for details. "
            "Use MockFacilitator for local development."
        )


class CloudLicenseProvider(BaseLicenseProvider):
    """Production license provider backed by the FairFetch Clearinghouse.

    Issues publisher-verified Usage Grants with persistent audit trail.
    This is a placeholder — the actual implementation is part of the
    FairFetch commercial cloud offering.
    """

    def __init__(
        self,
        *,
        api_key: str = "",
        publisher_id: str = "",
        base_url: str = "https://clearinghouse.fairfetch.dev/api/v1",
    ) -> None:
        self._api_key = api_key or os.getenv("FAIRFETCH_CLOUD_API_KEY", "")
        self._publisher_id = publisher_id or os.getenv("FAIRFETCH_PUBLISHER_ID", "")
        self._base_url = base_url

    async def issue_grant(
        self,
        *,
        content_url: str,
        content_hash: str,
        license_type: str,
        granted_to: str,
    ) -> UsageGrant:
        raise NotImplementedError(
            "CloudLicenseProvider requires a FairFetch Cloud subscription. "
            "See https://clearinghouse.fairfetch.dev for details. "
            "Use MockLicenseProvider for local development."
        )

    async def verify_grant(self, grant: UsageGrant) -> bool:
        raise NotImplementedError(
            "CloudLicenseProvider requires a FairFetch Cloud subscription. "
            "Use grant.verify() for local Ed25519 verification."
        )
