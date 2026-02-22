"""Ed25519 cryptographic signing for origin verification (EU AI Act compliance)."""

from __future__ import annotations

import base64
from dataclasses import dataclass

from nacl.encoding import Base64Encoder
from nacl.signing import SigningKey, VerifyKey


@dataclass(frozen=True, slots=True)
class SignatureBundle:
    signature: str  # base64-encoded
    public_key: str  # base64-encoded
    algorithm: str = "Ed25519"


class Ed25519Signer:
    """Signs content payloads with Ed25519 for provenance attestation."""

    def __init__(self, private_key_b64: str | None = None) -> None:
        if private_key_b64:
            raw = base64.b64decode(private_key_b64)
            self._signing_key = SigningKey(raw)
        else:
            self._signing_key = SigningKey.generate()

    @property
    def public_key_b64(self) -> str:
        return self._signing_key.verify_key.encode(encoder=Base64Encoder).decode()

    @property
    def private_key_b64(self) -> str:
        return base64.b64encode(bytes(self._signing_key)).decode()

    def sign(self, payload: bytes) -> SignatureBundle:
        signed = self._signing_key.sign(payload, encoder=Base64Encoder)
        sig_b64 = signed.signature.decode() if isinstance(signed.signature, bytes) else signed.signature
        return SignatureBundle(
            signature=sig_b64,
            public_key=self.public_key_b64,
        )


class Ed25519Verifier:
    """Verifies Ed25519 signatures against a public key."""

    def __init__(self, public_key_b64: str) -> None:
        raw = base64.b64decode(public_key_b64)
        self._verify_key = VerifyKey(raw)

    def verify(self, payload: bytes, signature_b64: str) -> bool:
        try:
            sig_bytes = base64.b64decode(signature_b64)
            self._verify_key.verify(payload, sig_bytes)
            return True
        except Exception:
            return False
