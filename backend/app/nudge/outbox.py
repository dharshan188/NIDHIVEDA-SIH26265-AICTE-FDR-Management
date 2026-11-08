"""Writes Nudge Ladder outbox rows. Callers pass their own Session and commit with their event, so an event and its
notice are stored together or not at all (the transactional outbox pattern)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from .clock import iso, now_ist
from .templates import EVENT_RUNG, KERNEL_KINDS, render


def notify(db: Session, audience: str, template: str, params: dict, *, ref: str | None = None, rung: str | None = None,
           institution_id: str | None = None, key: str | None = None, window: str | None = None, at: str | None = None,
           kind: str | None = None, parent_id: int | None = None, escalation_step: int = 0) -> m.Notification:
    """Idempotent when `key` is given: a second call with the same key returns the existing row."""
    if key:
        existing = db.scalars(select(m.Notification).where(m.Notification.key == key)).first() or next(
            (o for o in db.new if isinstance(o, m.Notification) and o.key == key), None)
        if existing:
            return existing
    if institution_id is None and audience.startswith("institution:"):
        institution_id = audience.split(":", 1)[1]
    n = m.Notification(at=at or iso(now_ist()), audience=audience, kind=kind or template, ref=ref, key=key, window=window,
                       rung=rung or EVENT_RUNG.get(template, "action"), template=template, params=params,
                       text=render(template, "en", params, "body"), text_hi=render(template, "hi", params, "body"),
                       institution_id=institution_id, parent_id=parent_id, escalation_step=escalation_step)
    db.add(n)
    return n


def kernel_notice(db: Session, n: dict) -> m.Notification:
    """A notice from the kernel's own outbox (holds, returns, rule questions...)."""
    label, label_hi, rung = KERNEL_KINDS.get(n["kind"], (n["kind"].replace("_", " ").capitalize(), n["kind"], "action"))
    return notify(db, n["to"], "kernel_notice", {"kind_label": {"en": label, "hi": label_hi}, "ref": n["ref"], "detail": n["text"]},
                  ref=n["ref"], rung=rung, at=n["at"], kind=n["kind"])


def title(n: m.Notification, lang: str = "en") -> str:
    if n.template and n.params is not None:
        return render(n.template, lang, n.params, "title")
    return n.kind.replace("_", " ").capitalize()
