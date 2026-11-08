"""Acknowledgement loop and escalation.

- An unacknowledged notice moves up one rung after acknowledgement.next_rung_after_days[rung] (a new notice, linked by
  parent_id, key up:<id>): info -> action -> deadline -> overdue.
- An overdue notice is copied to the next role in escalation.chain (institution -> AICTE officer -> competent authority)
  as soon as it is created, and again one step further after escalation.step_after_days without acknowledgement.
- Each step fires once (unique keys) and nothing fires once any notice in the same family has been acknowledged.
- Every step is written to the portal audit trail.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from .. import portal_audit
from . import policy as pol
from .clock import iso, now_ist, parse
from .ladder import next_rung
from .outbox import notify, title
from .recipients import CHAIN_AUDIENCE
from .templates import RUNG_LABEL, ROLE_LABEL


def root_of(db: Session, n: m.Notification) -> m.Notification:
    seen = set()
    while n.parent_id and n.parent_id not in seen:
        seen.add(n.id)
        n = db.get(m.Notification, n.parent_id)
    return n


def family_acked(db: Session, n: m.Notification) -> bool:
    root = root_of(db, n)
    stack, ids = [root.id], set()
    while stack:
        i = stack.pop()
        if i in ids:
            continue
        ids.add(i)
        stack.extend(db.scalars(select(m.Notification.id).where(m.Notification.parent_id == i)))
    return db.scalars(select(m.Notification.id).where(m.Notification.id.in_(ids), m.Notification.ack_at.is_not(None))).first() is not None


def _step_of(n: m.Notification) -> int:
    return n.escalation_step


def copy_up(db: Session, n: m.Notification, now: datetime, reason: str) -> int:
    """Copies an overdue notice to the next role in the chain. Returns 1 if a copy was made."""
    p = pol.active(db)
    chain = p["escalation"]["chain"]
    step = _step_of(n)
    if step + 1 >= len(chain):
        return 0
    root = root_of(db, n)
    key = f"esc:{root.id}:{step + 1}"
    if db.scalars(select(m.Notification.id).where(m.Notification.key == key)).first():
        return 0
    to = chain[step + 1]
    days = max(0, (now - parse(root.at)).days)
    subj = {"en": title(root, "en"), "hi": title(root, "hi")}
    c = notify(db, CHAIN_AUDIENCE[to], "escalation_copy",
               {"subject": subj, "from_role": {lang: ROLE_LABEL[lang][chain[step]] for lang in ("en", "hi")},
                "to_role": {lang: ROLE_LABEL[lang][to] for lang in ("en", "hi")}, "days": days},
               ref=root.ref, rung="overdue", key=key, at=iso(now), kind="escalation", parent_id=n.id, escalation_step=step + 1,
               institution_id=root.institution_id)
    db.flush()
    portal_audit.record(db, "notification_escalated", "system:nudge", {"from_id": n.id, "to_id": c.id, "type": "chain", "step": step + 1,
                                                                       "to_role": to, "reason": reason, "ref": root.ref})
    return 1


def sweep(db: Session, now: datetime | None = None) -> dict:
    now = now or now_ist()
    p = pol.active(db)
    after = p["acknowledgement"]["next_rung_after_days"]
    step_days = p["escalation"]["step_after_days"]
    out = {"rung_up": 0, "chain": 0, "stopped_by_ack": 0}
    open_rows = db.scalars(select(m.Notification).where(m.Notification.ack_at.is_(None), m.Notification.escalated_at.is_(None),
                                                        m.Notification.template.is_not(None), m.Notification.template != "digest")
                           .order_by(m.Notification.id)).all()
    for n in open_rows:
        age = (now - parse(n.at)).days
        if n.rung == "overdue":
            if age < step_days or _step_of(n) + 1 >= len(p["escalation"]["chain"]):
                continue
            if family_acked(db, n):
                out["stopped_by_ack"] += 1
                continue
            if copy_up(db, n, now, reason=f"not acknowledged for {age} days"):
                out["chain"] += 1
            n.escalated_at = iso(now)
            continue
        wait = after.get(n.rung)
        if wait is None or age < wait:
            continue
        if family_acked(db, n):
            out["stopped_by_ack"] += 1
            continue
        nxt = next_rung(n.rung)
        key = f"up:{n.id}"
        if db.scalars(select(m.Notification.id).where(m.Notification.key == key)).first() is None:
            root = root_of(db, n)
            u = notify(db, n.audience, "rung_up", {"subject": {"en": title(n, "en"), "hi": title(n, "hi")}, "first_sent": root.at[:10],
                                                   "days": age, "rung_label": {lang: RUNG_LABEL[lang][nxt] for lang in ("en", "hi")}},
                       ref=n.ref, rung=nxt, key=key, at=iso(now), kind="rung_up", parent_id=n.id, escalation_step=n.escalation_step,
                       institution_id=n.institution_id)
            db.flush()
            portal_audit.record(db, "notification_escalated", "system:nudge", {"from_id": n.id, "to_id": u.id, "type": "rung",
                                                                               "from_rung": n.rung, "to_rung": nxt, "reason": f"not acknowledged for {age} days"})
            out["rung_up"] += 1
            if nxt == "overdue":
                out["chain"] += copy_up(db, u, now, reason="reached overdue")
        n.escalated_at = iso(now)
    db.commit()
    return out
