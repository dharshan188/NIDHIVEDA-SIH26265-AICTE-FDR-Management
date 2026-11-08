"""MOCK Government SSO issuer (dev only). Stands in for e-Pramaan / DigiLocker-style OIDC.

Implements discovery, authorize (a sign-in page listing demo identities), token (with PKCE) and JWKS,
issuing RS256 ID tokens. The RSA key lives only in memory for the life of the process.
"""
from __future__ import annotations

import base64
import hashlib
import html
import secrets
import time
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import get_settings
from ..db import get_db
from ..deps import dev_only

router = APIRouter(prefix="/mock-oidc", tags=["mock-oidc (dev only)"], dependencies=[Depends(dev_only)])
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_KID = "mock-1"
_CODES: dict[str, dict] = {}


def issuer() -> str:
    return f"{get_settings().api_url}/mock-oidc"


def public_key():
    return _KEY.public_key()


@router.get("/.well-known/openid-configuration")
def discovery():
    return {"issuer": issuer(), "authorization_endpoint": f"{issuer()}/authorize", "token_endpoint": f"{issuer()}/token",
            "jwks_uri": f"{issuer()}/jwks", "id_token_signing_alg_values_supported": ["RS256"], "code_challenge_methods_supported": ["S256"]}


@router.get("/jwks")
def jwks():
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(_KEY.public_key(), as_dict=True)
    return {"keys": [{**jwk, "kid": _KID, "use": "sig", "alg": "RS256"}]}


@router.get("/authorize", response_class=HTMLResponse)
def authorize(client_id: str, redirect_uri: str, state: str, nonce: str, code_challenge: str, code_challenge_method: str,
              response_type: str = "code", scope: str = "openid", db: Session = Depends(get_db)):
    if client_id != get_settings().oidc_client_id or code_challenge_method != "S256" or response_type != "code":
        raise HTTPException(400, "invalid authorization request")
    users = db.scalars(select(m.User).where(m.User.sso_subject.is_not(None))).all()
    opts = "".join(f'<button name="sub" value="{html.escape(u.sso_subject)}">{html.escape(u.full_name)} <small>({u.role})</small></button>' for u in users)
    hidden = "".join(f'<input type="hidden" name="{k}" value="{html.escape(v)}">' for k, v in
                     {"redirect_uri": redirect_uri, "state": state, "nonce": nonce, "code_challenge": code_challenge}.items())
    return f"""<!doctype html><meta charset=utf-8><title>MOCK SSO</title>
<style>body{{font:15px system-ui;max-width:480px;margin:60px auto;color:#0f1f45}}.b{{background:#fff3cd;padding:10px;border-radius:8px}}
button{{display:block;width:100%;margin:8px 0;padding:12px;border:1px solid #0b5ed7;background:#fff;border-radius:8px;text-align:left;cursor:pointer}}</style>
<h2>Government SSO</h2><p class=b><b>SIMULATED</b> identity provider for development. Not e-Pramaan or DigiLocker.</p>
<p>Choose an identity (the provider is assumed to have completed its own MFA):</p><form method=post action="{issuer()}/authorize">{hidden}{opts}</form>"""


@router.post("/authorize")
def authorize_post(sub: str = Form(), redirect_uri: str = Form(), state: str = Form(), nonce: str = Form(), code_challenge: str = Form()):
    code = secrets.token_urlsafe(24)
    _CODES[code] = {"sub": sub, "nonce": nonce, "challenge": code_challenge, "exp": time.time() + 120}
    return RedirectResponse(f"{redirect_uri}?{urlencode({'code': code, 'state': state})}", status_code=302)


def exchange(code: str, verifier: str, client_id: str) -> dict:
    c = _CODES.pop(code, None)
    if not c or c["exp"] < time.time():
        raise HTTPException(400, "invalid or expired code")
    expect = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    if expect != c["challenge"]:
        raise HTTPException(400, "PKCE verification failed")
    now = int(time.time())
    tok = jwt.encode({"iss": issuer(), "sub": c["sub"], "aud": client_id, "iat": now, "exp": now + 300, "nonce": c["nonce"], "acr": "mfa"},
                     _KEY, algorithm="RS256", headers={"kid": _KID})
    return {"id_token": tok, "token_type": "Bearer"}


@router.post("/token")
def token(grant_type: str = Form(), code: str = Form(), code_verifier: str = Form(), client_id: str = Form()):
    if grant_type != "authorization_code":
        raise HTTPException(400, "unsupported grant")
    return exchange(code, code_verifier, client_id)


def issue_for_test(sub: str, nonce: str, aud: str | None = None) -> str:
    now = int(time.time())
    return jwt.encode({"iss": issuer(), "sub": sub, "aud": aud or get_settings().oidc_client_id, "iat": now, "exp": now + 300, "nonce": nonce,
                       "acr": "mfa"}, _KEY, algorithm="RS256", headers={"kid": _KID})
