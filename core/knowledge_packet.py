"""JSON-LD Knowledge Packet generation for AI-ready content distribution."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from core.signatures import Ed25519Signer, SignatureBundle


class DataLineage(BaseModel):
    """EU AI Act data lineage metadata."""

    source_url: str
    extraction_method: str = "trafilatura"
    extraction_timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    content_hash: str = ""
    license_type: str = "publisher-terms"
    usage_category: str = "summary"
    opt_out_respected: bool = True


class KnowledgePacket(BaseModel):
    """JSON-LD structured knowledge packet for AI agent consumption.

    Follows schema.org/Article with extensions for AI provenance tracking.
    """

    context: str = Field(default="https://schema.org", alias="@context")
    type: str = Field(default="Article", alias="@type")
    headline: str = ""
    author: str = ""
    canonical_url: str = ""
    date_published: str = ""
    summary: str = ""
    markdown_content: str = ""
    origin_signature: SignatureBundle | None = None
    data_lineage: DataLineage | None = None

    model_config = {"populate_by_name": True}

    def to_jsonld(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "@context": self.context,
            "@type": self.type,
            "headline": self.headline,
            "author": {"@type": "Person", "name": self.author} if self.author else None,
            "url": self.canonical_url,
            "datePublished": self.date_published,
            "description": self.summary,
            "articleBody": self.markdown_content,
        }
        if self.origin_signature:
            data["fairfetch:originSignature"] = {
                "algorithm": self.origin_signature.algorithm,
                "signature": self.origin_signature.signature,
                "publicKey": self.origin_signature.public_key,
            }
        if self.data_lineage:
            data["fairfetch:dataLineage"] = self.data_lineage.model_dump()
        return {k: v for k, v in data.items() if v is not None}


class KnowledgePacketBuilder:
    """Constructs a signed KnowledgePacket from converter and summarizer outputs."""

    def __init__(self, signer: Ed25519Signer | None = None) -> None:
        self._signer = signer

    def build(
        self,
        *,
        markdown: str,
        summary: str = "",
        title: str = "",
        author: str = "",
        url: str = "",
        date: str = "",
        license_type: str = "publisher-terms",
        usage_category: str = "summary",
    ) -> KnowledgePacket:
        content_hash = hashlib.sha256(markdown.encode()).hexdigest()

        signature: SignatureBundle | None = None
        if self._signer:
            signature = self._signer.sign(markdown.encode())

        lineage = DataLineage(
            source_url=url,
            content_hash=content_hash,
            license_type=license_type,
            usage_category=usage_category,
        )

        return KnowledgePacket(
            headline=title,
            author=author,
            canonical_url=url,
            date_published=date or datetime.now(UTC).isoformat(),
            summary=summary,
            markdown_content=markdown,
            origin_signature=signature,
            data_lineage=lineage,
        )
