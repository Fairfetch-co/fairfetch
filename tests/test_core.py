"""Tests for the core module: converter, signatures, knowledge packets (Green AI pillar)."""

from __future__ import annotations

import pytest

from core.converter import ContentConverter, ConversionResult
from core.knowledge_packet import KnowledgePacketBuilder
from core.signatures import Ed25519Signer, Ed25519Verifier


class TestContentConverter:
    """Green AI: content extraction eliminates redundant crawling."""

    async def test_from_html_extracts_text(self, sample_html: str):
        converter = ContentConverter()
        result = await converter.from_html(sample_html, url="https://example.com/article")

        assert isinstance(result, ConversionResult)
        assert len(result.markdown) > 0
        assert result.url == "https://example.com/article"

    async def test_from_html_strips_scripts(self, sample_html: str):
        converter = ContentConverter()
        result = await converter.from_html(sample_html)

        assert "console.log" not in result.markdown
        assert "tracking" not in result.markdown

    async def test_from_html_preserves_article_content(self, sample_html: str):
        converter = ContentConverter()
        result = await converter.from_html(sample_html)

        assert "1.5" in result.markdown or "temperature" in result.markdown.lower()


class TestEd25519Signatures:
    """Legal pillar: cryptographic origin attestation."""

    def test_sign_and_verify(self, signer: Ed25519Signer):
        payload = b"Hello, Fairfetch!"
        bundle = signer.sign(payload)

        assert bundle.algorithm == "Ed25519"
        assert len(bundle.signature) > 0
        assert len(bundle.public_key) > 0

        verifier = Ed25519Verifier(bundle.public_key)
        assert verifier.verify(payload, bundle.signature) is True

    def test_verify_fails_with_wrong_payload(self, signer: Ed25519Signer):
        bundle = signer.sign(b"original content")
        verifier = Ed25519Verifier(bundle.public_key)

        assert verifier.verify(b"tampered content", bundle.signature) is False

    def test_deterministic_public_key(self):
        signer = Ed25519Signer()
        pk1 = signer.public_key_b64
        pk2 = signer.public_key_b64
        assert pk1 == pk2

    def test_key_roundtrip(self):
        signer1 = Ed25519Signer()
        private_b64 = signer1.private_key_b64
        signer2 = Ed25519Signer(private_b64)

        assert signer1.public_key_b64 == signer2.public_key_b64

        payload = b"roundtrip test"
        bundle = signer1.sign(payload)
        verifier = Ed25519Verifier(signer2.public_key_b64)
        assert verifier.verify(payload, bundle.signature)


class TestKnowledgePacket:
    def test_build_packet(self, signer: Ed25519Signer):
        builder = KnowledgePacketBuilder(signer=signer)
        packet = builder.build(
            markdown="# Test\n\nHello world.",
            summary="A test article.",
            title="Test",
            author="Tester",
            url="https://example.com/test",
        )

        assert packet.headline == "Test"
        assert packet.author == "Tester"
        assert packet.summary == "A test article."
        assert packet.origin_signature is not None
        assert packet.data_lineage is not None
        assert packet.data_lineage.content_hash != ""

    def test_to_jsonld(self, signer: Ed25519Signer):
        builder = KnowledgePacketBuilder(signer=signer)
        packet = builder.build(
            markdown="Content here.",
            title="JSON-LD Test",
            url="https://example.com",
        )

        jsonld = packet.to_jsonld()
        assert jsonld["@context"] == "https://schema.org"
        assert jsonld["@type"] == "Article"
        assert jsonld["headline"] == "JSON-LD Test"
        assert "fairfetch:originSignature" in jsonld

    def test_packet_without_signer(self):
        builder = KnowledgePacketBuilder(signer=None)
        packet = builder.build(markdown="No signing.", url="https://example.com")

        assert packet.origin_signature is None
        jsonld = packet.to_jsonld()
        assert "fairfetch:originSignature" not in jsonld
