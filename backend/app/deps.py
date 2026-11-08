"""Request dependencies: session, CSRF, roles, institution scope."""
from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from . import models as m
from .config import get_settings
from .db import get_db
from .security import token_id

SESSION_COOKIE = "tl_session"
PREAUTH_COOKIE = "tl_preauth"
CSRF_COOKIE = "tl_csrf"
CSRF_HEADER = "x-csrf-token"
CLIENT_HEADER = "x-tl-client"
SAFE = {"GET", "HEAD", "OPTIONS"}


@dataclass
class Principal:
    user: m.User
    session: m.SessionRow

    @property
    def actor(self) -> str:
        return self.user.actor


def set_cookie(resp: Response, name: str, value: str, max_age: int, http_only: bool = True) -> None:
    resp.set_cookie(name, value, max_age=max_age, httponly=http_only, secure=get_settings().cookie_secure, samesite="strict", path="/")


def clear_cookie(resp: Response, name: str) -> None:
    resp.delete_cookie(name, path="/", secure=get_settings().cookie_secure, samesite="strict")


def require_client_header(request: Request) -> None:
    """Cross-site forms cannot set custom headers; every state-changing call must carry this one."""
    if request.method not in SAFE and request.headers.get(CLIENT_HEADER) != "web":
        raise HTTPException(403, "missing client header")


def _load(db: Session, token: str | None, kind: str) -> m.SessionRow | None:
    if not token:
        return None
    s = db.get(m.SessionRow, token_id(token))
    if not s or s.revoked or s.kind != kind:
        return None
    return s


def current(request: Request, response: Response, db: Session = Depends(get_db)) -> Principal:
    cfg = get_settings()
    s = _load(db, request.cookies.get(SESSION_COOKIE), "full")
    if s is None:
        raise HTTPException(401, "not signed in")
    now = datetime.now()
    if now > s.expires_at or now - s.last_seen > timedelta(minutes=cfg.session_idle_minutes):
        s.revoked = True
        db.commit()
        clear_cookie(response, SESSION_COOKIE)
        raise HTTPException(401, "session expired")
    if request.method not in SAFE:
        require_client_header(request)
        sent = request.headers.get(CSRF_HEADER, "")
        if not hmac.compare_digest(sent, s.csrf_token):
            raise HTTPException(403, "CSRF token missing or invalid")
    user = db.get(m.User, s.user_id)
    if not user or not user.active:
        raise HTTPException(401, "not signed in")
    s.last_seen = now
    db.commit()
    return Principal(user, s)


def preauth(request: Request, db: Session = Depends(get_db)) -> Principal:
    require_client_header(request)
    s = _load(db, request.cookies.get(PREAUTH_COOKIE), "preauth")
    if s is None or datetime.now() > s.expires_at:
        raise HTTPException(401, "sign-in step expired; start again")
    return Principal(db.get(m.User, s.user_id), s)


def require(*roles: str):
    def dep(p: Principal = Depends(current)) -> Principal:
        if p.user.role not in roles:
            raise HTTPException(403, "your role cannot do this")
        return p
    return dep


def require_kernel_role(*kernel_roles: str):
    def dep(p: Principal = Depends(current)) -> Principal:
        if p.user.kernel_role not in kernel_roles:
            raise HTTPException(403, f"needs one of: {', '.join(kernel_roles)}")
        return p
    return dep


def institution_scope(p: Principal, institution_id: str) -> None:
    """IDOR guard: an institution user may only touch its own institution's records."""
    if p.user.role == "INSTITUTION" and p.user.institution_id != institution_id:
        # 404, not 403: do not confirm that the other record exists
        raise HTTPException(404, "not found")


def dev_only() -> None:
    if not get_settings().is_dev:
        raise HTTPException(404, "not found")
