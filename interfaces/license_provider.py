"""BaseLicenseProvider — abstract interface for cryptographic Usage Grants.

A Usage Grant is an Ed25519-signed token that serves as a "Legal Receipt":
  - It proves the AI company accessed the content through a legitimate channel.
  - It records *what* was accessed (content_hash), *when*, and *under which terms*.
  - AI companies store these grants as proof of legal access, providing
    indemnity against future copyright litigation (Legal Safe Harbor).

Part of the FairFetch Open Standard.
"""

from __future__ import annotations

import hashlib
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from core.signatures import Ed25519Verifier, SignatureBundle


class UsageGrant(BaseModel):
    """Cryptographically signed proof of legal content access.

    AI companies retain this token as evidence of authorized usage
    under the publisher's stated license terms.
    """

    grant_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    content_url: str
    content_hash: str = Field(description="SHA-256 of the accessed content")
    license_type: str = Field(default="publisher-terms")
    granted_to: str = Field(default="", description="Payer wallet or agent identifier")
    granted_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    expires_at: str = Field(default="", description="ISO-8601 expiry, empty = perpetual")
    publisher_domain: str = ""
    signature: SignatureBundle | None = None

    def signing_payload(self) -> bytes:
        """Deterministic payload used for signing / verification."""
        canonical = (
            f"{self.grant_id}|{self.content_url}|{self.content_hash}|"
            f"{self.license_type}|{self.granted_to}|{self.granted_at}"
        )
        return canonical.encode()

    def to_header_value(self) -> str:
        """Compact representation suitable for the X-FairFetch-License-ID header."""
        sig_part = self.signature.signature[:16] if self.signature else "unsigned"
        return f"{self.grant_id}:{sig_part}"

    def verify(self) -> bool:
        """Verify the grant's own signature is valid."""
        if not self.signature:
            return False
        verifier = Ed25519Verifier(self.signature.public_key)
        return verifier.verify(self.signing_payload(), self.signature.signature)


class BaseLicenseProvider(ABC):
    """Abstract base for issuing and verifying Usage Grants."""

    @abstractmethod
    async def issue_grant(
        self,
        *,
        content_url: str,
        content_hash: str,
        license_type: str,
        granted_to: str,
    ) -> UsageGrant:
        """Issue a signed Usage Grant after successful payment."""
        ...

    @abstractmethod
    async def verify_grant(self, grant: UsageGrant) -> bool:
        """Verify an existing grant's cryptographic signature."""
        ...

    @staticmethod
    def hash_content(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()
