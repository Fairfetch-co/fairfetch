"""Mock License Facilitator — combines payment and usage-grant issuance for local dev.

Issues "Test-Only" legal grants alongside mock payment settlements.
Developers can exercise the full Green + Legal + Indemnity triple
without any live infrastructure.
"""

from __future__ import annotations

from core.signatures import Ed25519Signer
from interfaces.facilitator import BaseFacilitator, FacilitatorResult, PaymentRequirement
from interfaces.license_provider import BaseLicenseProvider, UsageGrant
from payments.mock_facilitator import MockFacilitator

TEST_GRANT_GRANTED_TO = "test-agent-local"


class MockLicenseProvider(BaseLicenseProvider):
    """Issues Ed25519-signed Usage Grants using a local ephemeral key."""

    def __init__(self, signer: Ed25519Signer | None = None) -> None:
        self._signer = signer or Ed25519Signer()

    async def issue_grant(
        self,
        *,
        content_url: str,
        content_hash: str,
        license_type: str = "publisher-terms",
        granted_to: str = "",
    ) -> UsageGrant:
        grant = UsageGrant(
            content_url=content_url,
            content_hash=content_hash,
            license_type=license_type,
            granted_to=granted_to or TEST_GRANT_GRANTED_TO,
            publisher_domain=_extract_domain(content_url),
        )
        sig = self._signer.sign(grant.signing_payload())
        grant.signature = sig
        return grant

    async def verify_grant(self, grant: UsageGrant) -> bool:
        return grant.verify()

    @property
    def public_key_b64(self) -> str:
        return self._signer.public_key_b64


class MockLicenseFacilitator:
    """Bundles MockFacilitator + MockLicenseProvider for dev convenience.

    A single object that handles both payment settlement and legal-grant
    issuance, mirroring the production FairFetch Managed Clearinghouse.
    """

    def __init__(self, signer: Ed25519Signer | None = None) -> None:
        self._signer = signer or Ed25519Signer()
        self.facilitator: BaseFacilitator = MockFacilitator()
        self.license_provider: BaseLicenseProvider = MockLicenseProvider(self._signer)

    async def settle_and_grant(
        self,
        *,
        payment_header: str,
        requirement: PaymentRequirement,
        content_url: str,
        content_hash: str,
        license_type: str = "publisher-terms",
    ) -> tuple[FacilitatorResult, UsageGrant | None]:
        """Settle payment and, if valid, issue a signed Usage Grant."""
        result = await self.facilitator.settle(payment_header, requirement)
        if not result.valid:
            return result, None

        grant = await self.license_provider.issue_grant(
            content_url=content_url,
            content_hash=content_hash,
            license_type=license_type,
            granted_to=result.payer,
        )
        return result, grant


def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse

        return urlparse(url).netloc
    except Exception:
        return ""
