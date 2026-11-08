from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..ratelimit import auth_limit
from .. import models as m
from .. import portal_audit
from ..config import get_settings
from ..db import get_db
from ..deps import (CSRF_COOKIE, PREAUTH_COOKIE, SESSION_COOKIE, Principal, clear_cookie, current, preauth, require_client_header,
                    set_cookie)
from ..security import (DscError, new_token, otp_code, otp_hash, otp_matches, token_id, totp_verify, verify_dsc, verify_password)
from . import oidc_mock

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("trustledger.auth")
GENERIC = "Sign-in failed. Check your details and try again, or try again later."
DEV_OTP_OUTBOX: dict[str, dict] = {}   # dev only: what the mock SMS provider "sent"


class LoginIn(BaseModel):
    username: str = Field(max_length=120)
    password: str = Field(max_length=200)
    role: str


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class DscIn(BaseModel):
    certificate_pem: str
    signature_b64: str


def _user_out(u: m.User, csrf: str | None = None) -> dict:
    out = {"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role, "kernel_role": u.kernel_role,
           "designation": u.designation, "institution_id": u.institution_id}
    if csrf:
        out["csrf_token"] = csrf
    return out


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    require_client_header(request)
    auth_limit(request, "login", body.username)
    cfg = get_settings()
    now = datetime.now()
    user = db.scalars(select(m.User).where(func.lower(m.User.username) == body.username.strip().lower())).first()
    ok = verify_password(user.password_hash if user else None, body.password)   # constant work either way
    if user and user.locked_until and user.locked_until > now:
        portal_audit.record(db, "login_refused_locked", "system:auth", {"username": user.username})
        db.commit()
        raise HTTPException(401, GENERIC)
    if not ok or not user or not user.active or user.role != body.role:
        if user:
            user.failed_attempts += 1
            if user.failed_attempts >= cfg.lockout_threshold:
                user.locked_until = now + timedelta(minutes=cfg.lockout_minutes)
                user.failed_attempts = 0
                portal_audit.record(db, "account_locked", "system:auth", {"username": user.username, "minutes": cfg.lockout_minutes})
        portal_audit.record(db, "login_failed", "system:auth", {"username": body.username.strip().lower()[:120]})
        db.commit()
        raise HTTPException(401, GENERIC)
    user.failed_attempts = 0
    user.locked_until = None
    token = new_token()
    db.add(m.SessionRow(id=token_id(token), user_id=user.id, kind="preauth", csrf_token=new_token(), created_at=now, last_seen=now,
                        expires_at=now + timedelta(minutes=cfg.preauth_minutes)))
    db.commit()
    set_cookie(response, PREAUTH_COOKIE, token, cfg.preauth_minutes * 60)
    methods = ["otp"] + (["totp"] if user.totp_secret_enc else []) + (["dsc"] if user.dsc_serial else [])
    return {"mfa_required": True, "methods": methods, "mobile_masked": user.mobile_masked}


def _complete(db: Session, response: Response, p: Principal, method: str) -> dict:
    cfg = get_settings()
    now = datetime.now()
    p.session.revoked = True
    token, csrf = new_token(), new_token()
    db.add(m.SessionRow(id=token_id(token), user_id=p.user.id, kind="full", mfa_method=method, csrf_token=csrf, created_at=now, last_seen=now,
                        expires_at=now + timedelta(hours=cfg.session_absolute_hours)))
    p.user.prev_login_at, p.user.last_login_at = p.user.last_login_at, now   # "what changed since you last looked" starts here
    portal_audit.record(db, "login_success", p.actor, {"username": p.user.username, "mfa": method})
    db.commit()
    clear_cookie(response, PREAUTH_COOKIE)
    set_cookie(response, SESSION_COOKIE, token, cfg.session_absolute_hours * 3600)
    set_cookie(response, CSRF_COOKIE, csrf, cfg.session_absolute_hours * 3600, http_only=False)
    return {"user": _user_out(p.user, csrf)}


@router.post("/otp/send")
def otp_send(request: Request, p: Principal = Depends(preauth), db: Session = Depends(get_db)):
    auth_limit(request, "otp", p.user.username)
    cfg = get_settings()
    now = datetime.now()
    recent = db.scalar(select(func.count()).select_from(m.OtpCode).where(m.OtpCode.user_id == p.user.id,
                                                                           m.OtpCode.created_at > now - timedelta(minutes=15)))
    if recent >= cfg.otp_max_sends_per_15min:
        raise HTTPException(429, "Too many OTP requests. Wait 15 minutes.")
    for old in db.scalars(select(m.OtpCode).where(m.OtpCode.user_id == p.user.id, m.OtpCode.used_at.is_(None))):
        old.used_at = now   # only the newest code is live
    code = otp_code()
    db.add(m.OtpCode(user_id=p.user.id, code_hash=otp_hash(p.user.id, code), created_at=now, expires_at=now + timedelta(minutes=cfg.otp_ttl_minutes)))
    db.commit()
    # MOCK SMS/e-mail provider: logs to the console in dev. A real gateway (e.g. NIC SMS) is planned.
    log.warning("[MOCK SMS] to %s for %s: OTP %s (valid %d min)", p.user.mobile_masked, p.user.username, code, cfg.otp_ttl_minutes)
    if cfg.is_dev:
        DEV_OTP_OUTBOX[p.user.username] = {"code": code, "at": now.isoformat(timespec="seconds")}
    return {"sent_to": p.user.mobile_masked, "expires_in_seconds": cfg.otp_ttl_minutes * 60}


@router.post("/otp/verify")
def otp_verify(body: CodeIn, request: Request, response: Response, p: Principal = Depends(preauth), db: Session = Depends(get_db)):
    auth_limit(request, "otp", p.user.username)
    cfg = get_settings()
    now = datetime.now()
    row = db.scalars(select(m.OtpCode).where(m.OtpCode.user_id == p.user.id, m.OtpCode.used_at.is_(None))
                     .order_by(m.OtpCode.id.desc()).limit(1)).first()
    if not row or row.expires_at < now or row.attempts >= cfg.otp_max_attempts:
        raise HTTPException(401, "Code expired or already used. Request a new one.")
    row.attempts += 1
    if not otp_matches(row.code_hash, p.user.id, body.code):
        if row.attempts >= cfg.otp_max_attempts:
            row.used_at = now
        db.commit()
        raise HTTPException(401, "Incorrect code.")
    row.used_at = now
    return _complete(db, response, p, "otp")


@router.post("/totp/verify")
def totp_login(body: CodeIn, request: Request, response: Response, p: Principal = Depends(preauth), db: Session = Depends(get_db)):
    auth_limit(request, "otp", p.user.username)
    if not totp_verify(p.user.totp_secret_enc, body.code):
        raise HTTPException(401, "Incorrect code.")
    return _complete(db, response, p, "totp")


@router.post("/dsc/challenge")
def dsc_challenge(p: Principal = Depends(preauth), db: Session = Depends(get_db)):
    if not p.user.dsc_serial:
        raise HTTPException(400, "no DSC registered for this account")
    p.session.dsc_challenge = secrets.token_hex(24)
    db.commit()
    return {"challenge": f"TL-LOGIN:{p.session.dsc_challenge}"}


@router.post("/dsc/verify")
def dsc_login(body: DscIn, request: Request, response: Response, p: Principal = Depends(preauth), db: Session = Depends(get_db)):
    auth_limit(request, "otp", p.user.username)
    if not p.session.dsc_challenge:
        raise HTTPException(400, "request a challenge first")
    msg = f"TL-LOGIN:{p.session.dsc_challenge}"
    p.session.dsc_challenge = None   # single use
    try:
        serial = verify_dsc(body.certificate_pem, body.signature_b64, msg)
    except DscError as e:
        db.commit()
        raise HTTPException(401, f"DSC check failed: {e}") from e
    if serial != p.user.dsc_serial:
        db.commit()
        raise HTTPException(401, "DSC check failed: certificate is not registered to this account")
    return _complete(db, response, p, "dsc")


@router.post("/logout")
def logout(response: Response, p: Principal = Depends(current), db: Session = Depends(get_db)):
    p.session.revoked = True
    portal_audit.record(db, "logout", p.actor, {})
    db.commit()
    clear_cookie(response, SESSION_COOKIE)
    clear_cookie(response, CSRF_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(p: Principal = Depends(current)):
    return {"user": _user_out(p.user, p.session.csrf_token), "mfa": p.session.mfa_method,
            "idle_timeout_seconds": get_settings().session_idle_minutes * 60}


# ------------------------------------------------------------------ Government SSO (OIDC authorisation code + PKCE)
def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _issuer() -> str:
    cfg = get_settings()
    return cfg.oidc_issuer or f"{cfg.api_url}/mock-oidc"


@router.get("/sso/start")
def sso_start(role: str, db: Session = Depends(get_db)):
    if role not in m.ROLES:
        raise HTTPException(400, "unknown role")
    cfg = get_settings()
    if not cfg.oidc_issuer and not cfg.is_dev:
        raise HTTPException(503, "SSO is not configured")
    state, nonce, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    db.add(m.OidcState(state=state, nonce=nonce, code_verifier=verifier, role=role, created_at=datetime.now()))
    db.commit()
    params = {"response_type": "code", "client_id": cfg.oidc_client_id, "redirect_uri": f"{cfg.api_url}/auth/sso/callback",
              "scope": "openid profile", "state": state, "nonce": nonce, "code_challenge_method": "S256",
              "code_challenge": _b64url(hashlib.sha256(verifier.encode()).digest())}
    return RedirectResponse(f"{_issuer()}/authorize?{urlencode(params)}", status_code=302)


@router.get("/sso/callback")
def sso_callback(code: str, state: str, request: Request, response: Response, db: Session = Depends(get_db)):
    auth_limit(request, "login")
    cfg = get_settings()
    st = db.get(m.OidcState, state)
    if not st or datetime.now() - st.created_at > timedelta(minutes=10):
        raise HTTPException(400, "SSO state invalid or expired")
    db.delete(st)
    db.commit()
    if cfg.oidc_issuer:   # real issuer: standard token request
        import httpx
        disc = httpx.get(f"{cfg.oidc_issuer}/.well-known/openid-configuration", timeout=10).json()
        if disc.get("issuer") != cfg.oidc_issuer:   # OIDC Discovery 1.0 §4.3: the document must name the configured issuer
            raise HTTPException(401, "SSO issuer discovery mismatch")
        tok = httpx.post(disc["token_endpoint"], data={"grant_type": "authorization_code", "code": code, "redirect_uri": f"{cfg.api_url}/auth/sso/callback",
                                                       "client_id": cfg.oidc_client_id, "client_secret": cfg.oidc_client_secret,
                                                       "code_verifier": st.code_verifier}, timeout=10).json()
        jwks = jwt.PyJWKClient(disc["jwks_uri"])
        key = jwks.get_signing_key_from_jwt(tok["id_token"]).key
    else:                 # dev: the mock issuer, called in-process; the token is still verified exactly as above
        tok = oidc_mock.exchange(code, st.code_verifier, cfg.oidc_client_id)
        key = oidc_mock.public_key()
    try:
        claims = jwt.decode(tok["id_token"], key, algorithms=["RS256"], audience=cfg.oidc_client_id, issuer=_issuer())
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"SSO token rejected: {e}") from e
    if claims.get("nonce") != st.nonce:
        raise HTTPException(401, "SSO token rejected: nonce mismatch")
    user = db.scalars(select(m.User).where(m.User.sso_subject == claims["sub"])).first()
    if not user or not user.active or user.role != st.role:
        raise HTTPException(401, GENERIC)
    now = datetime.now()
    # the identity provider performed MFA (acr claim); record it as the session's second factor
    if claims.get("acr") != "mfa":
        raise HTTPException(401, "SSO login did not use multi-factor authentication")
    tmp = m.SessionRow(id=token_id(new_token()), user_id=user.id, kind="preauth", csrf_token="", created_at=now, last_seen=now, expires_at=now)
    db.add(tmp)
    db.flush()
    resp = RedirectResponse(f"{cfg.public_url}/sso-complete", status_code=302)
    _complete(db, resp, Principal(user, tmp), "sso")
    return resp
