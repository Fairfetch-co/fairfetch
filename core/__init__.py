"""Fairfetch Core — the "Green AI" layer.

Handles HTML→Markdown conversion (eliminating redundant crawling),
Knowledge Packet construction (JSON-LD), and cryptographic signing.
The summarizer is a concrete BaseSummarizer implementation using LiteLLM.
"""

from core.converter import ContentConverter
from core.knowledge_packet import DataLineage, KnowledgePacket, KnowledgePacketBuilder
from core.signatures import Ed25519Signer, Ed25519Verifier
from core.summarizer import Summarizer

__all__ = [
    "ContentConverter",
    "DataLineage",
    "Ed25519Signer",
    "Ed25519Verifier",
    "KnowledgePacket",
    "KnowledgePacketBuilder",
    "Summarizer",
]
