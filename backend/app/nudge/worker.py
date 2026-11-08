"""The delivery worker. Safe to run concurrently or after a crash:

plan()      for each new outbox row: one delivery per (channel, recipient), chosen by rung, preferences and digest rules.
            Inserted under a unique constraint, so planning twice cannot create a second delivery.
send_due()  claims due deliveries with a lease, calls the provider with the delivery's idempotency key, records the result.
            A crash after the provider call but before the commit leaves the row 'sending'; when the lease expires the
            row is retried with the SAME key, and the provider returns the original message instead of sending again.
digest()    once per user per IST day: one digest notice for that day's informational items.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import crypto, portal_audit
from .. import models as m
from ..config import get_settings
from . import policy as pol
from .channels import OutMsg, ProviderError, provider
from .clock import as_ist, hhmm, iso, ist_date, next_at, now_ist, parse
from .ladder import channels_for
from .outbox import notify, title
from .recipients import role_of, users_for
from .templates import render

OPT_OUT_CHANNELS = ("email", "sms", "whatsapp", "push")


def _prefs(db: Session, user: m.User) -> m.NotificationPref:
    return db.get(m.NotificationPref, user.id) or m.NotificationPref(user_id=user.id, email=True, sms=True, whatsapp=True, push=True, digest=True)


def in_quiet_hours(now: datetime, policy: dict) -> bool:
    q = policy["quiet_hours"]
    t = as_ist(now).time()
    start, end = hhmm(q["start"]), hhmm(q["end"])
    return (t >= start or t < end) if start > end else (start <= t < end)


def plan(db: Session, now: datetime | None = None, limit: int = 500) -> int:
    now = now or now_ist()
    p = pol.active(db)
    made = 0
    rows = db.scalars(select(m.Notification).where(m.Notification.planned_at.is_(None)).order_by(m.Notification.id).limit(limit)).all()
    for n in rows:
        chans = channels_for(n.rung, p)
        batched = n.rung in p["digest"]["rungs"] and n.template != "digest"
        for u in users_for(db, n.audience):
            prefs = _prefs(db, u)
            for ch in chans:
                status, reason = "pending", None
                if ch in OPT_OUT_CHANNELS and not getattr(prefs, ch) and not (n.rung == "overdue" and ch == "email"):
                    status, reason = "skipped", "recipient turned this channel off"
                elif ch == "in_app" and batched and prefs.digest:
                    status, reason = "batched", "informational: goes into the daily digest"
                d = m.NotificationDelivery(notification_id=n.id, channel=ch, user_id=u.id, recipient_role=role_of(u, n.audience), status=status,
                                           reason=reason, idempotency_key=f"n{n.id}-{ch}-u{u.id}", next_attempt_at=iso(now), created_at=iso(now),
                                           simulated=provider(ch).simulated)
                try:
                    with db.begin_nested():
                        db.add(d)
                    made += 1
                except IntegrityError:   # already planned by another worker or an earlier, interrupted run
                    pass
        n.planned_at = iso(now)
        db.commit()
    return made


def _address(db: Session, u: m.User, channel: str) -> tuple[str | list[str] | None, str]:
    inst = db.get(m.Institution, u.institution_id) if u.institution_id else None
    if channel == "email":
        addr = u.username if "@" in u.username else (inst.email if inst else None)
        if not addr:
            return None, ""
        name, dom = addr.split("@", 1)
        return addr, f"{name[:2]}•••@{dom}"
    if channel in ("sms", "whatsapp"):
        num = crypto.decrypt_field(u.mobile) or (crypto.decrypt_field(inst.registered_mobile) if inst else None)
        return (num, crypto.mask(num)) if num else (None, "")
    if channel == "push":
        toks = [d.token for d in db.scalars(select(m.PushDevice).where(m.PushDevice.user_id == u.id))]
        return (toks, f"{len(toks)} device(s)") if toks else (None, "")
    return f"user:{u.id}", "notification centre"


def _message(db: Session, d: m.NotificationDelivery, n: m.Notification, u: m.User, link: str) -> OutMsg | None:
    to, masked = _address(db, u, d.channel)
    if to is None:
        return None
    lang = u.lang or "en"
    params = {**(n.params or {}), "link": link}
    tmpl = n.template or "kernel_notice"
    return OutMsg(channel=d.channel, idempotency_key=d.idempotency_key, to=to, to_masked=masked, to_role=d.recipient_role, lang=lang,
                  subject=render(tmpl, lang, params, "title") if n.template else title(n, lang), body=render(tmpl, lang, params, "body"),
                  short=render(tmpl, lang, params, "sms"), link=link, data={"path": link, "notification_id": n.id})


def _audit(db: Session, d: m.NotificationDelivery, n: m.Notification, status: str, detail: str = "") -> None:
    portal_audit.record(db, "notification_delivery", "system:nudge", {
        "notification_id": n.id, "delivery_id": d.id, "channel": d.channel, "recipient_role": d.recipient_role, "rung": n.rung,
        "template": n.template, "status": status, "provider": d.provider, "simulated": d.simulated, "attempt": d.attempts, "detail": detail[:200]})


def send_due(db: Session, now: datetime | None = None, limit: int = 200, crash_after_provider: str | None = None) -> dict:
    """`crash_after_provider` (a channel) is for the crash test only: it raises after that provider call, before the commit."""
    from .links import issue
    now = now or now_ist()
    p = pol.active(db)
    out = {"sent": 0, "deferred": 0, "failed": 0, "retry": 0, "skipped": 0}
    due = db.scalars(select(m.NotificationDelivery).where(or_(
        m.NotificationDelivery.status.in_(("pending", "deferred")) & (m.NotificationDelivery.next_attempt_at <= iso(now)),
        (m.NotificationDelivery.status == "sending") & (m.NotificationDelivery.lease_until <= iso(now)),
    )).order_by(m.NotificationDelivery.id).limit(limit)).all()
    for d in due:
        n = db.get(m.Notification, d.notification_id)
        q = p["quiet_hours"]
        if d.channel in q["channels"] and n.rung not in q["except_rungs"] and in_quiet_hours(now, p):
            d.status, d.reason, d.next_attempt_at = "deferred", f"quiet hours {q['start']}–{q['end']} IST", iso(next_at(now, hhmm(q["end"])))
            _audit(db, d, n, "deferred", d.reason)
            db.commit()
            out["deferred"] += 1
            continue
        # claim
        d.status, d.attempts, d.lease_until = "sending", d.attempts + 1, iso(now + timedelta(seconds=p["delivery"]["lease_seconds"]))
        db.commit()
        u = db.get(m.User, d.user_id)
        base = get_settings().public_url.rstrip("/")
        from .recipients import open_path
        link = base + open_path(n.audience, n.ref)
        if d.channel != "in_app":
            link = f"{base}/l/{issue(db, u.id, open_path(n.audience, n.ref), 'open', n.id, now)}"
        msg = _message(db, d, n, u, link)
        if msg is None:
            d.status, d.reason = "skipped", f"no {d.channel} address or device for this recipient"
            _audit(db, d, n, "skipped", d.reason)
            db.commit()
            out["skipped"] += 1
            continue
        db.commit()   # claim and link are stored before anything leaves the process
        prov = provider(d.channel)
        try:
            res = prov.send(db, msg)
        except ProviderError as e:
            backoff = p["delivery"]["retry_after_minutes"]
            if d.attempts >= p["delivery"]["max_attempts"]:
                d.status, d.reason = "failed", str(e)[:300]
                out["failed"] += 1
            else:
                d.status, d.reason = "pending", str(e)[:300]
                d.next_attempt_at = iso(now + timedelta(minutes=backoff[min(d.attempts - 1, len(backoff) - 1)]))
                out["retry"] += 1
            d.provider = prov.name
            _audit(db, d, n, d.status, str(e))
            db.commit()
            continue
        if crash_after_provider == d.channel:
            raise RuntimeError("simulated crash after the provider call, before the commit")
        d.status, d.provider, d.provider_ref, d.simulated, d.sent_at, d.lease_until = res.status, res.provider, res.provider_ref, res.simulated, iso(now), None
        d.reason = res.detail
        if res.status == "delivered":
            d.delivered_at, d.receipt_simulated = iso(now), res.simulated
        _audit(db, d, n, res.status + (" (SIMULATED)" if res.simulated else ""), res.detail)
        db.commit()
        out["sent"] += 1
    return out


def digest(db: Session, now: datetime | None = None) -> int:
    """One digest per user per IST day for batched informational items. Idempotent (key digest:<user>:<date>)."""
    now = now or now_ist()
    day = ist_date(now).isoformat()
    pending = db.scalars(select(m.NotificationDelivery).where(m.NotificationDelivery.status == "batched")).all()
    by_user: dict[int, list[m.NotificationDelivery]] = {}
    for d in pending:
        by_user.setdefault(d.user_id, []).append(d)
    made = 0
    for uid, items in by_user.items():
        notes = [db.get(m.Notification, d.notification_id) for d in items]
        summ_en = "; ".join(title(n, "en") for n in notes[:8]) + (" …" if len(notes) > 8 else "")
        summ_hi = "; ".join(title(n, "hi") for n in notes[:8]) + (" …" if len(notes) > 8 else "")
        dn = notify(db, f"user:{uid}", "digest", {"count": len(notes), "summary": {"en": summ_en, "hi": summ_hi}}, rung="info",
                    key=f"digest:{uid}:{day}", at=iso(now))
        db.flush()
        for d in items:
            d.status, d.digest_id, d.delivered_at, d.receipt_simulated = "digested", dn.id, iso(now), False
        made += 1
    db.commit()
    return made


def run_once(db: Session, now: datetime | None = None) -> dict:
    now = now or now_ist()
    planned = plan(db, now)
    sent = send_due(db, now)
    return {"planned": planned, **sent}


def acknowledge(db: Session, n: m.Notification, user: m.User, via: str, now: datetime | None = None) -> bool:
    """Opening in-app or clicking the action link acknowledges. First acknowledgement wins; later ones change nothing."""
    now = now or now_ist()
    n.read = True
    if n.ack_at:
        db.commit()
        return False
    n.ack_at, n.ack_by, n.ack_via = iso(now), role_of(user, n.audience), via
    portal_audit.record(db, "notification_acknowledged", "system:nudge", {"notification_id": n.id, "via": via, "by_role": n.ack_by,
                                                                          "rung": n.rung, "after_hours": round((now - parse(n.at)).total_seconds() / 3600, 2)})
    db.commit()
    return True
