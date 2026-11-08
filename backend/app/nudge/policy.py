"""Notification policy: defaults in backend/policy.json, overrides versioned in notify_policy_versions."""
from __future__ import annotations

import copy
import json
from datetime import datetime
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from .. import portal_audit
from ..config import BACKEND_DIR

RUNGS = ("info", "action", "deadline", "overdue")
CHANNELS = ("in_app", "email", "sms", "whatsapp", "push")


@lru_cache
def defaults() -> dict:
    return json.loads((BACKEND_DIR / "policy.json").read_text())


def active(db: Session) -> dict:
    row = db.scalars(select(m.NotifyPolicyVersion).order_by(m.NotifyPolicyVersion.id.desc()).limit(1)).first()
    return copy.deepcopy(row.policy if row else defaults())


def validate(p: dict) -> list[str]:
    errs: list[str] = []
    try:
        before = p["reminders"]["before_maturity_days"]
        if not before or any((not isinstance(d, int)) or d < 1 or d > 365 for d in before) or len(set(before)) != len(before):
            errs.append("reminders.before_maturity_days: distinct whole days between 1 and 365")
        after = p["reminders"]["after_missed_renewal_days"]
        if any((not isinstance(d, int)) or d < 1 or d > 90 for d in after):
            errs.append("reminders.after_missed_renewal_days: whole days between 1 and 90")
        lad = p["ladder"]
        if not (1 <= lad["deadline_within_days"] < lad["action_needed_within_days"] <= 365):
            errs.append("ladder: need 1 <= deadline_within_days < action_needed_within_days <= 365")
        for r in RUNGS:
            chans = p["channels"][r]
            if "in_app" not in chans or any(c not in CHANNELS for c in chans):
                errs.append(f"channels.{r}: in_app is always included; known channels are {', '.join(CHANNELS)}")
        if set(p["channels"]["overdue"]) != set(CHANNELS):
            errs.append("channels.overdue: overdue items use every channel")
        for r, d in p["acknowledgement"]["next_rung_after_days"].items():
            if r not in RUNGS or (d is not None and (not isinstance(d, int) or d < 1)):
                errs.append("acknowledgement.next_rung_after_days: rung -> whole days >= 1, or null")
        if p["escalation"]["hold_review_days"] != 30:
            errs.append("escalation.hold_review_days: fixed at 30 by the solution document (hold rule)")
        for k in ("start", "end"):
            hh, mm = p["quiet_hours"][k].split(":")
            if not (0 <= int(hh) < 24 and 0 <= int(mm) < 60):
                errs.append(f"quiet_hours.{k}: HH:MM")
        if "overdue" not in p["quiet_hours"]["except_rungs"]:
            errs.append("quiet_hours.except_rungs must include overdue")
        if not (1 <= p["action_links"]["ttl_hours"] <= 168):
            errs.append("action_links.ttl_hours: 1 to 168")
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        errs.append(f"policy is missing or has a malformed section: {e}")
    return errs


def publish(db: Session, new: dict, actor: str, reason: str) -> m.NotifyPolicyVersion:
    errs = validate(new)
    if errs:
        raise HTTPException(422, {"error": "InvalidPolicy", "problems": errs})
    old = active(db)
    if not portal_audit.changes(old, new):
        raise HTTPException(409, "the new policy is the same as the current one")
    row = m.NotifyPolicyVersion(created_at=datetime.now(), created_by=actor, reason=reason, policy=new)
    db.add(row)
    db.flush()
    diff = portal_audit.changes(old, new)
    changed = sorted({d["path"].split(".")[0] for d in diff})
    portal_audit.record(db, "notify_policy_changed", actor, {"version": row.id, "reason": reason, "sections": changed, "changes": diff,
                                                             "reminders": new["reminders"], "ladder": new["ladder"]})
    db.commit()
    return row
