"""One-click action links.

Token = <id>.<expiry unix>.<HMAC-SHA256 over id, expiry, user, path, action>. Only the SHA-256 of the token is stored.
A link is refused when it is malformed, forged, expired, already used, or opened by a different signed-in user.
Resolving a link never performs an action: it returns the record to open and acknowledges the notification. Approval
links say `step_up: "dsc"`; the approval endpoint itself still demands a fresh DSC signature over the gate decision.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models as m
from .. import portal_audit
from ..config import get_settings
from . import policy as pol
from .clock import iso, now_ist, parse

STEP_UP = {"approve": "dsc"}


def _sig(jti: str, exp: int, user_id: int, path: str, action: str) -> str:
    mac = hmac.new(get_settings().secret_key.encode(), f"link|{jti}|{exp}|{user_id}|{path}|{action}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def issue(db: Session, user_id: int, path: str, action: str = "open", notification_id: int | None = None, now: datetime | None = None,
          ttl_hours: int | None = None) -> str:
    now = now or now_ist()
    ttl = ttl_hours or pol.active(db)["action_links"]["ttl_hours"]
    jti = secrets.token_hex(12)
    exp_dt = now + timedelta(hours=ttl)
    exp = int(exp_dt.timestamp())
    token = f"{jti}.{exp}.{_sig(jti, exp, user_id, path, action)}"
    db.add(m.ActionToken(id=jti, token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user_id, notification_id=notification_id,
                         path=path, action=action, created_at=iso(now), expires_at=iso(exp_dt)))
    db.flush()
    return token


def resolve(db: Session, token: str, user: m.User, now: datetime | None = None) -> dict:
    now = now or now_ist()

    def refuse(code: int, why: str, jti: str | None = None):
        portal_audit.record(db, "action_link_refused", f"user:{user.id}", {"jti": jti, "reason": why})
        db.commit()
        raise HTTPException(code, why)

    parts = token.split(".")
    if len(parts) != 3 or not parts[1].isdigit():
        refuse(400, "malformed link")
    jti, exp_s, sig = parts
    row = db.get(m.ActionToken, jti)
    if row is None or not hmac.compare_digest(row.token_hash, hashlib.sha256(token.encode()).hexdigest()):
        refuse(400, "unknown or altered link", jti)
    if not hmac.compare_digest(sig, _sig(jti, int(exp_s), row.user_id, row.path, row.action)):
        refuse(400, "link signature does not verify", jti)
    if now >= parse(row.expires_at) or now.timestamp() >= int(exp_s):
        refuse(410, "this link has expired; open the portal and sign in instead", jti)
    if row.used_at:
        refuse(409, "this link has already been used", jti)
    if row.user_id != user.id:
        refuse(403, "this link was issued to another user", jti)
    row.used_at = iso(now)
    acked = False
    if row.notification_id:
        from .worker import acknowledge
        n = db.get(m.Notification, row.notification_id)
        if n:
            acked = acknowledge(db, n, user, "link", now)
    portal_audit.record(db, "action_link_opened", f"user:{user.id}", {"jti": jti, "path": row.path, "action": row.action,
                                                                     "notification_id": row.notification_id})
    db.commit()
    return {"path": row.path, "action": row.action, "step_up": STEP_UP.get(row.action), "acknowledged": acked,
            "note": "Opening a link never performs an action. Approvals still need your DSC signature on the record."}
