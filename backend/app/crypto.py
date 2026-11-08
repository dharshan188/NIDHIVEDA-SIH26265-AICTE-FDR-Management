"""Encryption at rest: envelope encryption for documents, field-level encryption for PII.

Keys
- The master key (KEK) comes from TL_MASTER_KEY (32 bytes, base64) through the `Kms` interface. `LocalKms` keeps it in
  process memory; a cloud KMS (AWS KMS, GCP KMS, a government HSM) implements the same wrap/unwrap calls.
- Every document gets its own random 256-bit data key (DEK). The document is encrypted with AES-256-GCM under the DEK;
  the DEK is stored only wrapped by the KEK. Stealing the object store and the database is not enough without the KEK.
- PII fields use a field key derived from the KEK (HKDF, label "tl-field-v1"). Values are stored as `enc:v1:<base64>`
  and shown masked (last 4 characters). A keyed HMAC "blind index" allows exact-match look-ups without decrypting.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .config import get_settings

ENC_PREFIX = "enc:v1:"
DOC_ALG = "AES-256-GCM/envelope-v1"


class Kms(Protocol):
    key_id: str

    def wrap(self, dek: bytes, context: bytes) -> bytes: ...
    def unwrap(self, wrapped: bytes, context: bytes) -> bytes: ...


class LocalKms:
    """KEK held in memory, loaded from an environment variable. Wrap = AES-256-GCM(KEK) over the DEK, bound to a context."""

    def __init__(self, master_key: bytes, key_id: str = "local-kek-1"):
        if len(master_key) != 32:
            raise ValueError("TL_MASTER_KEY must decode to exactly 32 bytes")
        self._aead = AESGCM(master_key)
        self.key_id = key_id
        self._master = master_key

    def wrap(self, dek: bytes, context: bytes) -> bytes:
        nonce = os.urandom(12)
        return nonce + self._aead.encrypt(nonce, dek, b"dek|" + context)

    def unwrap(self, wrapped: bytes, context: bytes) -> bytes:
        return self._aead.decrypt(wrapped[:12], wrapped[12:], b"dek|" + context)

    def derive(self, label: str) -> bytes:
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=label.encode()).derive(self._master)


@lru_cache
def kms() -> LocalKms:
    s = get_settings()
    return LocalKms(base64.b64decode(s.master_key), s.master_key_id)


def reset_keys() -> None:
    """Tests switch keys to prove data is unreadable without the right one."""
    kms.cache_clear()
    _field_key.cache_clear()
    _index_key.cache_clear()


# ------------------------------------------------------------------ documents (envelope encryption)
@dataclass
class Sealed:
    ciphertext: bytes
    wrapped_dek: str   # base64
    nonce: str         # base64
    kek_id: str
    alg: str = DOC_ALG


def seal_document(plaintext: bytes, context: str) -> Sealed:
    """Encrypts one document under a fresh data key. `context` (the object key) is authenticated, so a ciphertext cannot be
    swapped for another document's without failing decryption."""
    dek = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    ct = AESGCM(dek).encrypt(nonce, plaintext, context.encode())
    k = kms()
    return Sealed(ct, base64.b64encode(k.wrap(dek, context.encode())).decode(), base64.b64encode(nonce).decode(), k.key_id)


def open_document(ciphertext: bytes, wrapped_dek: str, nonce: str, context: str) -> bytes:
    dek = kms().unwrap(base64.b64decode(wrapped_dek), context.encode())
    return AESGCM(dek).decrypt(base64.b64decode(nonce), ciphertext, context.encode())


# ------------------------------------------------------------------ PII fields
@lru_cache
def _field_key() -> AESGCM:
    return AESGCM(kms().derive("tl-field-v1"))


@lru_cache
def _index_key() -> bytes:
    return kms().derive("tl-blind-index-v1")


def encrypt_field(value: str | None) -> str | None:
    if value is None or value == "" or is_encrypted(value):
        return value
    nonce = os.urandom(12)
    return ENC_PREFIX + base64.b64encode(nonce + _field_key().encrypt(nonce, value.encode(), b"field")).decode()


def decrypt_field(value: str | None) -> str | None:
    if not is_encrypted(value):
        return value
    raw = base64.b64decode(value[len(ENC_PREFIX):])  # type: ignore[index]
    return _field_key().decrypt(raw[:12], raw[12:], b"field").decode()


def is_encrypted(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(ENC_PREFIX)


def blind_index(value: str) -> str:
    return hmac.new(_index_key(), value.strip().upper().encode(), hashlib.sha256).hexdigest()


def mask(value: str | None, keep: int = 4) -> str:
    """Shown in the UI and in audit records: only the last `keep` characters."""
    if not value:
        return ""
    plain = decrypt_field(value) or ""
    return "•" * max(len(plain) - keep, 2) + plain[-keep:]


# PII keys that can appear inside kernel event data and signed bank payloads.
PII_KEYS = frozenset({"account", "beneficiary_account", "remitter_account", "paying_to", "known_accounts", "pan", "mobile"})


def seal_pii(obj: Any) -> Any:
    """Copy of `obj` with every PII value encrypted. Used before JSON leaves the process for storage."""
    if isinstance(obj, dict):
        return {k: (_seal_value(v) if k in PII_KEYS else seal_pii(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [seal_pii(v) for v in obj]
    return obj


def open_pii(obj: Any) -> Any:
    """Inverse of seal_pii: restores the exact plaintext structure (so hashes over it still verify)."""
    if isinstance(obj, dict):
        return {k: (_open_value(v) if k in PII_KEYS else open_pii(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [open_pii(v) for v in obj]
    return obj


def mask_pii(obj: Any) -> Any:
    """For API output: PII values (already decrypted by open_pii) reduced to their last 4 characters."""
    if isinstance(obj, dict):
        return {k: (_mask_value(v) if k in PII_KEYS else mask_pii(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [mask_pii(v) for v in obj]
    return obj


def _mask_value(v: Any) -> Any:
    if isinstance(v, str):
        return mask(v)
    if isinstance(v, list):
        return [_mask_value(x) for x in v]
    if isinstance(v, dict):
        return {k: _mask_value(x) for k, x in v.items()}
    return v


def _seal_value(v: Any) -> Any:
    if isinstance(v, str):
        return encrypt_field(v)
    if isinstance(v, list):
        return [_seal_value(x) for x in v]
    if isinstance(v, dict):
        return {k: _seal_value(x) for k, x in v.items()}
    return v


def _open_value(v: Any) -> Any:
    if isinstance(v, str):
        return decrypt_field(v)
    if isinstance(v, list):
        return [_open_value(x) for x in v]
    if isinstance(v, dict):
        return {k: _open_value(x) for k, x in v.items()}
    return v
