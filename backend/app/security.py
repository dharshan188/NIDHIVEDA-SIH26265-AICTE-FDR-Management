"""Authentication primitives: Argon2id, opaque session tokens, OTP, TOTP, DSC certificate checks."""
from __future__ import annotations

import base64
import os
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyotp
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509.oid import NameOID

from .config import BACKEND_DIR, get_settings

_ph = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2, type=Type.ID)
# Verified against when the username does not exist, so the response time does not reveal it.
_DUMMY_HASH = _ph.hash(secrets.token_urlsafe(16))


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(stored: str | None, pw: str) -> bool:
    try:
        return _ph.verify(stored or _DUMMY_HASH, pw) and stored is not None
    except (VerificationError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def otp_hash(user_id: int, code: str) -> str:
    return hmac.new(get_settings().secret_key.encode(), f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def otp_matches(stored: str, user_id: int, code: str) -> bool:
    return hmac.compare_digest(stored, otp_hash(user_id, code))


# ------------------------------------------------------------------ TOTP (RFC 6238)
def _fernet() -> Fernet:
    return Fernet(get_settings().data_key.encode())


def new_totp_secret() -> tuple[str, str]:
    raw = pyotp.random_base32()
    return raw, _fernet().encrypt(raw.encode()).decode()


def totp_secret(enc: str) -> str:
    return _fernet().decrypt(enc.encode()).decode()


def totp_verify(enc: str | None, code: str) -> bool:
    if not enc or not code.isdigit():
        return False
    return pyotp.TOTP(totp_secret(enc)).verify(code, valid_window=1)


# ------------------------------------------------------------------ DSC (X.509 certificate + signature over a challenge)
DEVCERTS = Path(os.environ.get("TL_DEVCERTS_DIR") or BACKEND_DIR / "devcerts")


class DscError(Exception):
    pass


def trust_anchors() -> list[x509.Certificate]:
    """Production: the CCA India root and licensed CA chain (planned). Dev: a locally generated test CA."""
    p = DEVCERTS / "dev-ca.pem"
    return [x509.load_pem_x509_certificate(p.read_bytes())] if p.exists() else []


def ensure_dev_ca() -> None:
    """Dev only: creates a throwaway CA (gitignored). This is the SIMULATED DSC issuer."""
    if (DEVCERTS / "dev-ca.pem").exists():
        return
    DEVCERTS.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SIMULATED DSC CA (dev only)"),
                      x509.NameAttribute(NameOID.COMMON_NAME, "Trust Ledger Dev CA")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False, key_encipherment=False, data_encipherment=False,
                                         key_agreement=False, key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
            .sign(key, hashes.SHA256()))
    (DEVCERTS / "dev-ca.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    kp = DEVCERTS / "dev-ca.key"
    kp.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    kp.chmod(0o600)


def issue_dev_dsc(username: str, valid_days: int = 730) -> str:
    """Dev only: issue a Class-3-like test certificate for a user. Returns the certificate serial (hex)."""
    ensure_dev_ca()
    ca_cert = x509.load_pem_x509_certificate((DEVCERTS / "dev-ca.pem").read_bytes())
    ca_key = serialization.load_pem_private_key((DEVCERTS / "dev-ca.key").read_bytes(), None)
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, username), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SIMULATED DSC")]))
            .issuer_name(ca_cert.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=valid_days))
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False, data_encipherment=False,
                                         key_agreement=False, key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .sign(ca_key, hashes.SHA256()))
    safe = username.replace("@", "_at_")
    (DEVCERTS / f"{safe}.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    kp = DEVCERTS / f"{safe}.key"
    kp.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    kp.chmod(0o600)
    return format(cert.serial_number, "x")


def dev_dsc_sign(username: str, message: str) -> dict:
    """Dev only: what a DSC token + signer utility would do on the user's machine."""
    safe = username.replace("@", "_at_")
    cert_pem = (DEVCERTS / f"{safe}.pem").read_text()
    key = serialization.load_pem_private_key((DEVCERTS / f"{safe}.key").read_bytes(), None)
    sig = key.sign(message.encode(), ec.ECDSA(hashes.SHA256()))
    return {"certificate_pem": cert_pem, "signature_b64": base64.b64encode(sig).decode()}


def verify_dsc(cert_pem: str, signature_b64: str, message: str) -> str:
    """Checks: issued by a trust anchor, inside its validity window, digitalSignature key usage, and
    a valid signature over `message`. Returns the certificate serial (hex). CRL/OCSP: planned."""
    try:
        cert = x509.load_pem_x509_certificate(cert_pem.encode())
    except ValueError as e:
        raise DscError("certificate could not be parsed") from e
    now = datetime.now(timezone.utc)
    if not (cert.not_valid_before_utc <= now <= cert.not_valid_after_utc):
        raise DscError("certificate is outside its validity period")
    issuer = next((a for a in trust_anchors() if a.subject == cert.issuer), None)
    if issuer is None:
        raise DscError("certificate is not issued by a trusted CA")
    try:
        ik = issuer.public_key()
        if isinstance(ik, rsa.RSAPublicKey):
            ik.verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), cert.signature_hash_algorithm)
        else:
            ik.verify(cert.signature, cert.tbs_certificate_bytes, ec.ECDSA(cert.signature_hash_algorithm))
    except InvalidSignature as e:
        raise DscError("certificate signature does not chain to the trusted CA") from e
    try:
        ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
        if not ku.digital_signature:
            raise DscError("certificate is not for digital signatures")
    except x509.ExtensionNotFound as e:
        raise DscError("certificate has no key usage") from e
    sig = base64.b64decode(signature_b64)
    pub = cert.public_key()
    try:
        if isinstance(pub, ec.EllipticCurvePublicKey):
            pub.verify(sig, message.encode(), ec.ECDSA(hashes.SHA256()))
        elif isinstance(pub, rsa.RSAPublicKey):
            pub.verify(sig, message.encode(), padding.PKCS1v15(), hashes.SHA256())
        else:
            raise DscError("unsupported key type")
    except InvalidSignature as e:
        raise DscError("signature does not verify with the certificate key") from e
    return format(cert.serial_number, "x")


def utcnow() -> datetime:
    return datetime.now()

