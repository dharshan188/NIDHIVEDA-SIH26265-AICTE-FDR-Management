"""Settings from environment variables (prefix TL_). Secrets are never hard-coded.

In dev, any secret left empty is generated once and kept in backend/.dev-secrets.json
(gitignored) so restarts keep the same keys. In prod, empty secrets are a startup error.
"""
from __future__ import annotations

import json
import secrets
import sys
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TL_", env_file=BACKEND_DIR / ".env", extra="ignore")

    env: str = "dev"
    database_url: str = f"sqlite:///{BACKEND_DIR / 'trustledger.db'}"
    secret_key: str = ""
    data_key: str = ""
    sim_bank_seed: str = ""
    demo_password: str = ""
    cookie_secure: bool = True
    session_idle_minutes: int = 15
    session_absolute_hours: int = 8
    preauth_minutes: int = 5
    otp_ttl_minutes: int = 5
    otp_max_sends_per_15min: int = 5
    otp_max_attempts: int = 5
    lockout_threshold: int = 5
    lockout_minutes: int = 15
    checkpoint_path: str = "~/.trust-ledger/checkpoints.jsonl"
    kernel_path: str = str(BACKEND_DIR.parent / "trust-ledger-kernel")
    oidc_issuer: str = ""
    oidc_client_id: str = "trust-ledger"
    oidc_client_secret: str = ""
    public_url: str = "http://localhost:5173"
    # Nudge Ladder providers: "sim" = provider simulator (SIMULATED, nothing leaves the machine)
    email_provider: str = "sim"   # sim | smtp
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "NIDHIVEDA <no-reply@nidhiveda.local>"
    smtp_starttls: bool = False
    smtp_sink: bool = True        # true for Mailpit: messages land in a local inbox, labelled SIMULATED
    sms_provider: str = "sim"     # sim | http
    sms_url: str = ""
    sms_api_key: str = ""
    sms_sender: str = "AICTEF"
    sms_dlt_entity: str = ""
    whatsapp_provider: str = "sim"  # sim | cloud
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    whatsapp_template: str = "fdr_notice"
    push_provider: str = "sim"    # sim | fcm
    fcm_credentials: str = ""     # Firebase service-account JSON file (push_provider=fcm)
    provider_webhook_secret: str = ""  # HMAC key for delivery-receipt webhooks
    # rate limits (per client address and per account; ratelimit.py)
    rate_login_per_min: int = 20
    rate_otp_per_5min: int = 20
    rate_link_per_min: int = 30
    trust_proxy: bool = False     # trust X-Forwarded-For (only behind the configured reverse proxy)
    # documents: envelope encryption, object store, malware scan
    master_key: str = ""          # KEK, 32 bytes base64 (TL_MASTER_KEY); wraps every document key and derives the PII field key
    master_key_id: str = "local-kek-1"
    object_store: str = "fs"      # fs | s3
    object_dir: str = ""          # fs store root (default backend/objects)
    s3_endpoint: str = "localhost:8333"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "tl-documents"
    s3_secure: bool = False
    scanner: str = "stub"         # stub (dev only) | clamd
    clamd_host: str = "localhost"
    clamd_port: int = 3310
    api_url: str = "http://localhost:5173/api"
    timezone: str = "Asia/Kolkata"

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    @property
    def kernel_dir(self) -> Path:
        p = Path(self.kernel_path)
        return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


def _fill_dev_secrets(s: Settings) -> None:
    path = BACKEND_DIR / ".dev-secrets.json"
    stored = json.loads(path.read_text()) if path.exists() else {}
    changed = False
    for name, make in (
        ("secret_key", lambda: secrets.token_urlsafe(48)),
        ("data_key", lambda: __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet.generate_key().decode()),
        ("sim_bank_seed", lambda: secrets.token_hex(32)),
        ("provider_webhook_secret", lambda: secrets.token_urlsafe(32)),
        ("master_key", lambda: __import__("base64").b64encode(secrets.token_bytes(32)).decode()),
        ("oidc_client_secret", lambda: secrets.token_urlsafe(24)),
    ):
        if not getattr(s, name):
            if name not in stored:
                stored[name] = make()
                changed = True
            setattr(s, name, stored[name])
    if changed:
        path.write_text(json.dumps(stored, indent=1))
        path.chmod(0o600)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_dev:
        _fill_dev_secrets(s)
    else:
        missing = [n for n in ("secret_key", "data_key", "master_key") if not getattr(s, n)]
        if missing:
            raise RuntimeError(f"missing required secrets in environment: {', '.join('TL_' + m.upper() for m in missing)}")
    if str(s.kernel_dir) not in sys.path:
        sys.path.insert(0, str(s.kernel_dir))
    return s
