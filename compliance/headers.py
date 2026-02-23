"""EU AI Act + FairFetch compliance HTTP headers for content provenance and licensing.

Standardized header names:
  X-FairFetch-Origin-Signature  — Ed25519 sig of the content body
  X-FairFetch-License-ID        — Usage Grant compact identifier
  X-FairFetch-Usage-Category    — Permitted usage tier (search_engine_indexing, summary, rag, etc.)
  X-FairFetch-Version           — Protocol version (e.g. 0.2)
  X-Data-Origin-Verified        — EU AI Act origin attestation
  X-AI-License-Type             — Content license terms
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.signatures import SignatureBundle
from interfaces.license_provider import ComplianceLevel, UsageCategory, get_compliance_level


def _sanitize_header_value(value: str) -> str:
    """Remove CR/LF to prevent HTTP response splitting (RFC 7230)."""
    return value.replace("\r", "").replace("\n", "").strip()


@dataclass(frozen=True, slots=True)
class ComplianceHeaders:
    """Generates HTTP headers for EU AI Act 2026 compliance + FairFetch protocol."""

    origin_verified: bool = True
    license_type: str = "publisher-terms"
    usage_category: str = field(default=UsageCategory.SUMMARY)
    signature: SignatureBundle | None = None
    lineage_url: str = ""
    content_hash: str = ""
    license_id: str = ""

    def to_dict(self) -> dict[str, str]:
        try:
            cat = UsageCategory(self.usage_category)
            compliance = get_compliance_level(cat)
        except ValueError:
            compliance = ComplianceLevel.STANDARD

        headers: dict[str, str] = {
            "X-Data-Origin-Verified": _sanitize_header_value(str(self.origin_verified).lower()),
            "X-AI-License-Type": _sanitize_header_value(self.license_type),
            "X-FairFetch-Usage-Category": _sanitize_header_value(self.usage_category),
            "X-FairFetch-Compliance-Level": _sanitize_header_value(compliance.value),
            "X-FairFetch-Version": "0.2",
        }

        if self.signature:
            headers["X-FairFetch-Origin-Signature"] = _sanitize_header_value(
                self.signature.signature
            )
            headers["X-Origin-Public-Key"] = _sanitize_header_value(self.signature.public_key)
            headers["X-Origin-Signature-Algorithm"] = _sanitize_header_value(
                self.signature.algorithm
            )

        if self.lineage_url:
            headers["X-Content-Lineage"] = _sanitize_header_value(self.lineage_url)

        if self.content_hash:
            headers["X-Content-Hash"] = _sanitize_header_value(f"sha256:{self.content_hash}")

        if self.license_id:
            headers["X-FairFetch-License-ID"] = _sanitize_header_value(self.license_id)

        return headers
