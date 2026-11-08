"""Signature helpers for bank evidence.

Ed25519 is used here as a stand-in for the real mechanism (DSC / PKCS#7
signatures, SFMS-authenticated messages, or a bank host-to-host channel).
What the kernel proves is the control logic around signatures: who may sign,
from when, and what happens when that authority ends or is compromised.
"""
from __future__ import annotations

import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .audit import canonical


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def unb64(s: str) -> bytes:
    return base64.b64decode(s.encode())


class TestBankSigner:
    """Simulates a bank's signing desk (holds the private key). Test/demo only."""

    def __init__(self, bank: str, key_id: str) -> None:
        self.bank = bank
        self.key_id = key_id
        self._sk = Ed25519PrivateKey.generate()

    @property
    def public_key_b64(self) -> str:
        from cryptography.hazmat.primitives import serialization

        raw = self._sk.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return b64(raw)

    def sign(self, kind: str, payload: dict, signed_at: str) -> dict:
        envelope = {"kind": kind, "bank": self.bank, "key_id": self.key_id, "signed_at": signed_at, "payload": payload}
        sig = self._sk.sign(canonical(envelope).encode())
        return {**envelope, "signature": b64(sig)}


def verify_envelope(envelope: dict, public_key_b64: str) -> bool:
    body = {k: envelope[k] for k in ("kind", "bank", "key_id", "signed_at", "payload")}
    try:
        Ed25519PublicKey.from_public_bytes(unb64(public_key_b64)).verify(
            unb64(envelope["signature"]), canonical(body).encode()
        )
        return True
    except (InvalidSignature, ValueError, KeyError):
        return False
