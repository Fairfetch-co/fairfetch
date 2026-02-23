"""BaseLicenseProvider — abstract interface for cryptographic Usage Grants.

A Usage Grant is an Ed25519-signed token that serves as a "Legal Receipt":
  - It proves the AI company accessed the content through a legitimate channel.
  - It records *what* was accessed (content_hash), *when*, and *under which terms*.
  - AI companies store these grants as proof of legal access, providing
    indemnity against future copyright litigation (Legal Safe Harbor).

Usage Categories control *how* the content may be used (summary, RAG,
training, etc.) with escalating compliance and pricing tiers.

Part of the FairFetch Open Standard.
"""

from __future__ import annotations

import hashlib
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from core.signatures import Ed25519Verifier, SignatureBundle


class UsageCategory(StrEnum):
    """Defines the permitted use of accessed content.

    Categories are listed in order of increasing price (first = free/cheapest):
      - SEARCH_ENGINE_INDEXING: Search engine indexing (free when site owner allows)
      - SUMMARY:   Display a short summary or snippet
      - RAG:       Retrieval-Augmented Generation / search grounding
      - RESEARCH:  Academic or internal research use
      - TRAINING:  Model fine-tuning or pre-training
      - COMMERCIAL: Redistribution or commercial derivative works (highest tier)
    """

    SEARCH_ENGINE_INDEXING = "search_engine_indexing"
    SUMMARY = "summary"
    RAG = "rag"
    RESEARCH = "research"
    TRAINING = "training"
    COMMERCIAL = "commercial"


class ComplianceLevel(StrEnum):
    """Compliance tier associated with a usage category."""

    STANDARD = "standard"
    ELEVATED = "elevated"
    STRICT = "strict"


USAGE_CATEGORY_META: dict[UsageCategory, dict[str, object]] = {
    UsageCategory.SEARCH_ENGINE_INDEXING: {
        "compliance_level": ComplianceLevel.STANDARD,
        "price_multiplier": 0,
        "requires_audit_trail": False,
        "description": "Search engine crawling for indexing (free when site owner allows)",
    },
    UsageCategory.SUMMARY: {
        "compliance_level": ComplianceLevel.STANDARD,
        "price_multiplier": 1,
        "requires_audit_trail": False,
        "description": "Short summary or snippet display",
    },
    UsageCategory.RAG: {
        "compliance_level": ComplianceLevel.STANDARD,
        "price_multiplier": 2,
        "requires_audit_trail": False,
        "description": "Retrieval-Augmented Generation / search grounding",
    },
    UsageCategory.RESEARCH: {
        "compliance_level": ComplianceLevel.ELEVATED,
        "price_multiplier": 3,
        "requires_audit_trail": True,
        "description": "Academic or internal research use",
    },
    UsageCategory.TRAINING: {
        "compliance_level": ComplianceLevel.STRICT,
        "price_multiplier": 5,
        "requires_audit_trail": True,
        "description": "Model fine-tuning or pre-training",
    },
    UsageCategory.COMMERCIAL: {
        "compliance_level": ComplianceLevel.STRICT,
        "price_multiplier": 10,
        "requires_audit_trail": True,
        "description": "Redistribution or commercial derivative works",
    },
}


def get_compliance_level(category: UsageCategory) -> ComplianceLevel:
    meta = USAGE_CATEGORY_META[category]
    return ComplianceLevel(str(meta["compliance_level"]))


def get_price_multiplier(category: UsageCategory) -> int:
    val = USAGE_CATEGORY_META[category]["price_multiplier"]
    if isinstance(val, int):
        return val
    return int(str(val))


class UsageGrant(BaseModel):
    """Cryptographically signed proof of legal content access.

    AI companies retain this token as evidence of authorized usage
    under the content owner's stated license terms and usage category.
    """

    grant_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    content_url: str
    content_hash: str = Field(description="SHA-256 of the accessed content")
    license_type: str = Field(default="publisher-terms")
    usage_category: str = Field(
        default=UsageCategory.SUMMARY,
        description="Permitted use: search_engine_indexing, summary, rag, research, training, commercial",  # noqa: E501
    )
    granted_to: str = Field(default="", description="Payer wallet or agent identifier")
    granted_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    expires_at: str = Field(default="", description="ISO-8601 expiry, empty = perpetual")
    publisher_domain: str = ""
    signature: SignatureBundle | None = None

    def signing_payload(self) -> bytes:
        """Deterministic payload used for signing / verification."""
        canonical = (
            f"{self.grant_id}|{self.content_url}|{self.content_hash}|"
            f"{self.license_type}|{self.usage_category}|"
            f"{self.granted_to}|{self.granted_at}"
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
        usage_category: str = UsageCategory.SUMMARY,
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
