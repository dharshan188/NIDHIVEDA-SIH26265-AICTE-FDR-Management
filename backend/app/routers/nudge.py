"""/nudge: notification centre with the ladder, acknowledgement, action links, preferences, policy, "what changed",
escalation view and the health panel. /providers: delivery-receipt webhooks from real providers."""
from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..ratelimit import auth_limit
from .. import models as m
from .. import portal_audit
from ..config import get_settings
from ..db import get_db
from ..deps import Principal, current, require
from ..nudge import insights, links
from ..nudge import policy as pol
from ..nudge.clock import iso, now_ist
from ..nudge.escalation import root_of
from ..nudge.outbox import title
from ..nudge.recipients import audiences
from ..nudge.templates import RUNG_LABEL
from ..nudge.worker import acknowledge

router = APIRouter(tags=["nudge ladder"])


def _mine(db: Session, p: Principal, nid: int) -> m.Notification:
    n = db.get(m.Notification, nid)
    if not n or n.audience not in audiences(p.user):
        raise HTTPException(404, "not found")
    return n


def _row(db: Session, n: m.Notification, user: m.User) -> dict:
    lang = user.lang or "en"
    mine = db.scalars(select(m.NotificationDelivery).where(m.NotificationDelivery.notification_id == n.id,
                                                           m.NotificationDelivery.user_id == user.id)).all()
    return {"id": n.id, "at": n.at, "kind": n.kind, "template": n.template, "rung": n.rung, "rung_label": RUNG_LABEL[lang].get(n.rung, n.rung),
            "title": title(n, lang), "text": n.text_hi if lang == "hi" and n.text_hi else n.text, "text_en": n.text, "text_hi": n.text_hi,
            "ref": n.ref, "window": n.window, "read": n.read, "ack_at": n.ack_at, "ack_via": n.ack_via, "escalated_at": n.escalated_at,
            "escalation_step": n.escalation_step, "parent_id": n.parent_id, "audience": n.audience,
            "deliveries": [{"channel": d.channel, "status": d.status, "simulated": d.simulated, "provider": d.provider, "reason": d.reason,
                            "sent_at": d.sent_at, "delivered_at": d.delivered_at, "receipt_simulated": d.receipt_simulated} for d in mine]}


@router.get("/nudge/centre")
def centre(p: Principal = Depends(current), db: Session = Depends(get_db), rung: str = "", status: str = "", ref: str = "", page: int = 1,
           size: int = 20):
    aud = audiences(p.user)
    q = select(m.Notification).where(m.Notification.audience.in_(aud))
    if ref:
        q = q.where(m.Notification.ref == ref)
    if rung:
        q = q.where(m.Notification.rung == rung)
    if status == "open":
        q = q.where(m.Notification.ack_at.is_(None))
    elif status == "acknowledged":
        q = q.where(m.Notification.ack_at.is_not(None))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(m.Notification.at.desc(), m.Notification.id.desc()).offset((page - 1) * size).limit(size)).all()
    ladder = dict(db.execute(select(m.Notification.rung, func.count()).where(m.Notification.audience.in_(aud), m.Notification.ack_at.is_(None))
                             .group_by(m.Notification.rung)).all())
    return {"total": total, "open_by_rung": {r: ladder.get(r, 0) for r in ("info", "action", "deadline", "overdue")},
            "items": [_row(db, n, p.user) for n in rows], "lang": p.user.lang}


@router.get("/nudge/notifications/{nid}")
def detail(nid: int, p: Principal = Depends(current), db: Session = Depends(get_db)):
    n = _mine(db, p, nid)
    root = root_of(db, n)
    fam, stack = [], [root]
    while stack:
        x = stack.pop(0)
        fam.append(x)
        stack.extend(db.scalars(select(m.Notification).where(m.Notification.parent_id == x.id).order_by(m.Notification.id)))
    lang = p.user.lang or "en"
    return {"notification": _row(db, n, p.user),
            "ladder": [{"id": x.id, "at": x.at, "rung": x.rung, "rung_label": RUNG_LABEL[lang].get(x.rung, x.rung), "audience": x.audience,
                        "template": x.template, "title": title(x, lang), "ack_at": x.ack_at, "escalation_step": x.escalation_step} for x in fam]}


@router.post("/nudge/notifications/{nid}/open")
def open_notice(nid: int, p: Principal = Depends(current), db: Session = Depends(get_db)):
    n = _mine(db, p, nid)
    first = acknowledge(db, n, p.user, "open")
    return {"acknowledged": True, "first": first, "ack_at": n.ack_at}


class LinkIn(BaseModel):
    token: str = Field(min_length=10, max_length=300)


@router.post("/nudge/links/resolve")
def resolve_link(body: LinkIn, request: Request, p: Principal = Depends(current), db: Session = Depends(get_db)):
    auth_limit(request, "link", p.user.username)
    return links.resolve(db, body.token, p.user)


class PrefsIn(BaseModel):
    lang: str = Field(pattern="^(en|hi)$")
    email: bool = True
    sms: bool = True
    whatsapp: bool = True
    push: bool = True
    digest: bool = True


@router.get("/nudge/prefs")
def get_prefs(p: Principal = Depends(current), db: Session = Depends(get_db)):
    pr = db.get(m.NotificationPref, p.user.id)
    base = {"email": True, "sms": True, "whatsapp": True, "push": True, "digest": True}
    if pr:
        base = {k: getattr(pr, k) for k in base}
    return {"lang": p.user.lang, **base, "in_app": True,
            "note": "In-app notices cannot be switched off. Overdue items are always e-mailed."}


@router.put("/nudge/prefs")
def put_prefs(body: PrefsIn, p: Principal = Depends(current), db: Session = Depends(get_db)):
    pr = db.get(m.NotificationPref, p.user.id) or m.NotificationPref(user_id=p.user.id)
    for k in ("email", "sms", "whatsapp", "push", "digest"):
        setattr(pr, k, getattr(body, k))
    db.merge(pr)
    p.user.lang = body.lang
    portal_audit.record(db, "notification_prefs_changed", p.actor, body.model_dump())
    db.commit()
    return get_prefs(p, db)


@router.get("/nudge/policy")
def get_policy(p: Principal = Depends(current), db: Session = Depends(get_db)):
    row = db.scalars(select(m.NotifyPolicyVersion).order_by(m.NotifyPolicyVersion.id.desc()).limit(1)).first()
    return {"policy": pol.active(db), "version": row.id if row else 0, "updated_by": row.created_by if row else "backend/policy.json defaults",
            "updated_at": row.created_at.isoformat(timespec="seconds") if row else None, "editable": p.user.role == "AICTE_OFFICIAL"}


class PolicyIn(BaseModel):
    policy: dict
    reason: str = Field(min_length=5, max_length=500)


@router.put("/nudge/policy")
def put_policy(body: PolicyIn, p: Principal = Depends(require("AICTE_OFFICIAL")), db: Session = Depends(get_db)):
    row = pol.publish(db, body.policy, p.actor, body.reason)
    return {"version": row.id, "policy": row.policy}


@router.get("/nudge/what-changed")
def what_changed(p: Principal = Depends(current), db: Session = Depends(get_db), since: str | None = None):
    return insights.what_changed(db, p.user, since)


@router.get("/nudge/health")
def health(p: Principal = Depends(require("AICTE_OFFICIAL", "AUDITOR")), db: Session = Depends(get_db), days: int = 30):
    return insights.health(db, days)


@router.get("/nudge/escalations")
def escalations(p: Principal = Depends(require("AICTE_OFFICIAL", "AUDITOR")), db: Session = Depends(get_db), limit: int = 50):
    """Every escalated family: the original notice and each rung / chain step after it, with acknowledgement."""
    steps = db.scalars(select(m.Notification).where(m.Notification.template.in_(("rung_up", "escalation_copy")))
                       .order_by(m.Notification.at.desc()).limit(500)).all()
    seen, out = set(), []
    for s in steps:
        root = root_of(db, s)
        if root.id in seen:
            continue
        seen.add(root.id)
        fam, stack = [], [root]
        while stack:
            x = stack.pop(0)
            fam.append(x)
            stack.extend(db.scalars(select(m.Notification).where(m.Notification.parent_id == x.id).order_by(m.Notification.id)))
        out.append({"root_id": root.id, "ref": root.ref, "institution_id": root.institution_id, "title": title(root),
                    "acknowledged": any(x.ack_at for x in fam), "steps": [{"id": x.id, "at": x.at, "rung": x.rung, "audience": x.audience,
                                                                            "template": x.template, "step": x.escalation_step,
                                                                            "ack_at": x.ack_at, "ack_by": x.ack_by} for x in fam]})
        if len(out) >= limit:
            break
    return {"items": out, "total": len(out)}


# ------------------------------------------------------------------ provider delivery receipts
class ReceiptIn(BaseModel):
    provider_ref: str | None = None
    idempotency_key: str | None = None
    status: str = Field(pattern="^(delivered|failed|read)$")
    at: str | None = None


@router.post("/providers/receipts/{channel}")
async def receipt(channel: str, request: Request, db: Session = Depends(get_db)):
    """Signed by the provider integration with TL_PROVIDER_WEBHOOK_SECRET (X-TL-Signature: hex HMAC-SHA256 of the body).
    Only this path ever sets a non-simulated delivered_at."""
    raw = await request.body()
    want = hmac.new(get_settings().provider_webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(want, request.headers.get("x-tl-signature", "")):
        raise HTTPException(401, "bad signature")
    body = ReceiptIn.model_validate_json(raw)
    q = select(m.NotificationDelivery).where(m.NotificationDelivery.channel == channel)
    q = q.where(m.NotificationDelivery.provider_ref == body.provider_ref) if body.provider_ref else q.where(
        m.NotificationDelivery.idempotency_key == body.idempotency_key)
    d = db.scalars(q).first()
    if not d:
        raise HTTPException(404, "unknown message")
    at = body.at or iso(now_ist())
    if body.status in ("delivered", "read"):
        d.status, d.delivered_at, d.receipt_simulated = "delivered", at, d.simulated
    else:
        d.status, d.reason = "failed", "provider reported failure"
    portal_audit.record(db, "notification_receipt", f"provider:{d.provider}", {"delivery_id": d.id, "channel": channel, "status": body.status,
                                                                              "simulated": d.simulated, "recipient_role": d.recipient_role})
    db.commit()
    return {"ok": True}
