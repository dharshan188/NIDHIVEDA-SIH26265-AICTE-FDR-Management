"""Permitted field updates and scrutiny observations.

Field updates: only the fields in PERMITTED can change, only by the roles listed, only in the FDR states listed. Every change
keeps before and after (masked for PII), the user, the time and a reason, in the hash-chained portal audit and in
field_changes. Instrument facts the ledger holds (bank, number, amount, dates) are never editable: a correction is a new
submission or a renewal.

Observations: an officer records a categorised observation on an FDR; the institution replies (status answered); the
officer closes it. Each step is audited and notifies the other side through the Nudge Ladder.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import crypto, portal_audit
from .. import models as m
from ..db import get_db
from ..deps import Principal, current, institution_scope, require
from ..nudge import notify
from ..nudge.clock import iso, now_ist
from ..nudge.templates import CATEGORY_LABEL

router = APIRouter(tags=["records"])


@dataclass(frozen=True)
class Rule:
    roles: frozenset[str]
    pattern: str
    pii: bool = False
    fdr_states: frozenset[str] | None = None   # FDR fields: states in which the field may change
    label: str = ""


PERMITTED: dict[tuple[str, str], Rule] = {
    ("institution", "email"): Rule(frozenset({"INSTITUTION", "AICTE_OFFICIAL"}), r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", label="Official e-mail"),
    ("institution", "phone"): Rule(frozenset({"INSTITUTION", "AICTE_OFFICIAL"}), r"^\+?[0-9 ()-]{8,20}$", label="Office phone"),
    ("institution", "principal"): Rule(frozenset({"INSTITUTION"}), r"^.{3,80}$", label="Principal / head of institution"),
    ("institution", "registered_mobile"): Rule(frozenset({"INSTITUTION", "AICTE_OFFICIAL"}), r"^\+91[6-9][0-9]{9}$", pii=True,
                                               label="Registered mobile (OTP and SMS notices)"),
    ("institution", "pan"): Rule(frozenset({"AICTE_OFFICIAL"}), r"^[A-Z]{5}[0-9]{4}[A-Z]$", pii=True, label="PAN of the trust / society"),
    ("fdr", "branch"): Rule(frozenset({"INSTITUTION", "AICTE_OFFICIAL"}), r"^.{3,80}$", fdr_states=frozenset({"pending", "discrepancy"}),
                            label="Issuing branch"),
    ("fdr", "rate_bp"): Rule(frozenset({"INSTITUTION"}), r"^[1-9][0-9]{1,3}$", fdr_states=frozenset({"pending", "discrepancy"}),
                             label="Interest rate (basis points)"),
}
NOT_EDITABLE = {"bank", "instrument_no", "amount_paise", "issue_date", "maturity_date", "status", "institution_id", "aicte_id", "name"}


class ChangeIn(BaseModel):
    field: str
    value: str = Field(max_length=200)
    reason: str = Field(min_length=5, max_length=500)


@router.get("/records/fields")
def permitted_fields(p: Principal = Depends(current)):
    return {"fields": [{"entity": e, "field": f, "label": r.label, "roles": sorted(r.roles), "pii": r.pii,
                        "fdr_states": sorted(r.fdr_states) if r.fdr_states else None, "you_can_edit": p.user.role in r.roles}
                       for (e, f), r in PERMITTED.items()], "never_editable": sorted(NOT_EDITABLE)}


def _entity(db: Session, p: Principal, entity: str, eid: str):
    if entity == "institution":
        obj = db.get(m.Institution, eid)
        inst_id = eid
    elif entity == "fdr":
        obj = db.get(m.Fdr, eid)
        inst_id = obj.institution_id if obj else None
    else:
        raise HTTPException(404, "unknown record type")
    if not obj:
        raise HTTPException(404, "not found")
    institution_scope(p, inst_id)
    return obj, inst_id


@router.patch("/records/{entity}/{eid}")
def change_field(entity: str, eid: str, body: ChangeIn, p: Principal = Depends(current), db: Session = Depends(get_db)):
    obj, inst_id = _entity(db, p, entity, eid)
    rule = PERMITTED.get((entity, body.field))
    if rule is None:
        why = "held by the ledger; submit a corrected FDR or a renewal instead" if body.field in NOT_EDITABLE else "not an editable field"
        raise HTTPException(422, {"error": "NotPermitted", "message": f"{entity}.{body.field} is {why}"})
    if p.user.role not in rule.roles:
        raise HTTPException(403, f"your role cannot change {rule.label.lower()}")
    if rule.fdr_states and obj.status not in rule.fdr_states:
        raise HTTPException(409, {"error": "StateError", "message": f"{rule.label} can change only while the FDR is {' or '.join(sorted(rule.fdr_states))}"})
    value = body.value.strip()
    if not re.fullmatch(rule.pattern, value):
        raise HTTPException(422, f"{rule.label}: value does not have the expected format")
    current_raw = getattr(obj, body.field)
    before_plain = crypto.decrypt_field(current_raw) if rule.pii else (None if current_raw is None else str(current_raw))
    if before_plain == value:
        raise HTTPException(409, "the new value is the same as the current one")
    shown_before = crypto.mask(before_plain) if rule.pii else before_plain
    shown_after = crypto.mask(value) if rule.pii else value
    setattr(obj, body.field, crypto.encrypt_field(value) if rule.pii else (int(value) if body.field == "rate_bp" else value))
    at = iso(now_ist())
    ev = portal_audit.record(db, "field_changed", p.actor, {"entity": entity, "entity_id": eid, "institution_id": inst_id, "field": body.field,
                                                            "before": shown_before, "after": shown_after, "reason": body.reason,
                                                            "pii": rule.pii}, at=at)
    db.flush()
    row = m.FieldChange(entity=entity, entity_id=eid, field=body.field, before=shown_before, after=shown_after, actor=p.actor, at=at,
                        reason=body.reason, portal_event_seq=ev.seq)
    db.add(row)
    db.commit()
    return {"change": _change(row)}


def _change(r: m.FieldChange) -> dict:
    return {"id": r.id, "entity": r.entity, "entity_id": r.entity_id, "field": r.field, "before": r.before, "after": r.after, "actor": r.actor,
            "at": r.at, "reason": r.reason, "audit_seq": r.portal_event_seq}


@router.get("/records/{entity}/{eid}/changes")
def changes(entity: str, eid: str, p: Principal = Depends(current), db: Session = Depends(get_db)):
    _entity(db, p, entity, eid)
    rows = db.scalars(select(m.FieldChange).where(m.FieldChange.entity == entity, m.FieldChange.entity_id == eid).order_by(m.FieldChange.id)).all()
    return {"items": [_change(r) for r in rows]}


# ------------------------------------------------------------------ scrutiny observations
class ObservationIn(BaseModel):
    category: str = Field(pattern="^(missing_document|mismatch|query)$")
    text: str = Field(min_length=5, max_length=2000)


class ReplyIn(BaseModel):
    text: str = Field(min_length=2, max_length=2000)


def _obs(o: m.Observation, replies: list[m.ObservationReply]) -> dict:
    return {"id": o.id, "fdr_id": o.fdr_id, "institution_id": o.institution_id, "category": o.category,
            "category_label": CATEGORY_LABEL["en"][o.category], "text": o.text, "status": o.status, "raised_by": o.raised_by, "raised_at": o.raised_at,
            "closed_by": o.closed_by, "closed_at": o.closed_at,
            "replies": [{"id": r.id, "author": r.author, "side": r.side, "at": r.at, "text": r.text} for r in replies]}


def _load(db: Session, p: Principal, oid: int) -> m.Observation:
    o = db.get(m.Observation, oid)
    if not o:
        raise HTTPException(404, "not found")
    institution_scope(p, o.institution_id)
    return o


@router.get("/fdrs/{fid}/observations")
def list_for_fdr(fid: str, p: Principal = Depends(current), db: Session = Depends(get_db)):
    f = db.get(m.Fdr, fid)
    if not f:
        raise HTTPException(404, "not found")
    institution_scope(p, f.institution_id)
    rows = db.scalars(select(m.Observation).where(m.Observation.fdr_id == fid).order_by(m.Observation.id)).all()
    return {"items": [_obs(o, db.scalars(select(m.ObservationReply).where(m.ObservationReply.observation_id == o.id).order_by(m.ObservationReply.id)).all())
                      for o in rows]}


@router.get("/observations")
def list_all(p: Principal = Depends(current), db: Session = Depends(get_db), status: str = ""):
    q = select(m.Observation).order_by(m.Observation.id.desc())
    if p.user.role == "INSTITUTION":
        q = q.where(m.Observation.institution_id == p.user.institution_id)
    if status:
        q = q.where(m.Observation.status == status)
    return {"items": [_obs(o, []) for o in db.scalars(q.limit(200))]}


@router.post("/fdrs/{fid}/observations")
def raise_observation(fid: str, body: ObservationIn, p: Principal = Depends(require("AICTE_OFFICIAL")), db: Session = Depends(get_db)):
    f = db.get(m.Fdr, fid)
    if not f:
        raise HTTPException(404, "not found")
    at = iso(now_ist())
    o = m.Observation(fdr_id=fid, institution_id=f.institution_id, category=body.category, text=body.text, status="open", raised_by=p.actor, raised_at=at)
    db.add(o)
    db.flush()
    portal_audit.record(db, "observation_raised", p.actor, {"observation_id": o.id, "fdr_id": fid, "institution_id": f.institution_id,
                                                            "category": body.category}, at=at)
    notify(db, f"institution:{f.institution_id}", "observation_raised",
           {"fdr_id": fid, "category": {"en": CATEGORY_LABEL["en"][body.category], "hi": CATEGORY_LABEL["hi"][body.category]}, "text": body.text[:300]},
           ref=fid, at=at)
    db.commit()
    return {"observation": _obs(o, [])}


@router.post("/observations/{oid}/replies")
def reply(oid: int, body: ReplyIn, p: Principal = Depends(require("INSTITUTION", "AICTE_OFFICIAL")), db: Session = Depends(get_db)):
    o = _load(db, p, oid)
    if o.status == "closed":
        raise HTTPException(409, "this observation is closed")
    at = iso(now_ist())
    side = "institution" if p.user.role == "INSTITUTION" else "aicte"
    db.add(m.ObservationReply(observation_id=o.id, author=p.actor, side=side, at=at, text=body.text))
    if side == "institution":
        o.status = "answered"
        inst = db.get(m.Institution, o.institution_id)
        notify(db, "aicte", "observation_answered", {"fdr_id": o.fdr_id, "institution": inst.name if inst else o.institution_id, "text": body.text[:300]},
               ref=o.fdr_id, at=at, institution_id=o.institution_id)
    portal_audit.record(db, "observation_replied", p.actor, {"observation_id": o.id, "fdr_id": o.fdr_id, "institution_id": o.institution_id,
                                                             "side": side, "status": o.status}, at=at)
    db.commit()
    return list_for_fdr(o.fdr_id, p, db)


@router.post("/observations/{oid}/close")
def close(oid: int, p: Principal = Depends(require("AICTE_OFFICIAL")), db: Session = Depends(get_db)):
    o = _load(db, p, oid)
    if o.status == "closed":
        raise HTTPException(409, "already closed")
    o.status, o.closed_by, o.closed_at = "closed", p.actor, iso(now_ist())
    portal_audit.record(db, "observation_closed", p.actor, {"observation_id": o.id, "fdr_id": o.fdr_id, "institution_id": o.institution_id})
    db.commit()
    return {"observation": _obs(o, [])}
