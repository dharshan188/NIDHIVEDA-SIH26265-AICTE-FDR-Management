"""Releases, payments, payees, holds, rules, policy, reconciliation, bank views, reports, audit trail."""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..crypto import mask_pii
from ..ledger import event_data
from .. import models as m
from .. import portal_audit
from .. import serialize as S
from ..bank.simulator import BANKS
from ..config import get_settings
from ..db import get_db
from ..deps import Principal, current, institution_scope, require, require_kernel_role
from ..domain import release as rel
from ..domain.amounts import penalty_proposal, required_deposit
from ..domain.common import domain_http, now_iso
from ..ledger import LEDGER

router = APIRouter(tags=["ledger"])
OFFICIAL = require("AICTE_OFFICIAL")


# ------------------------------------------------------------------ release requests
class ReleaseIn(BaseModel):
    fdr_id: str | None = None
    obligation_id: str | None = None
    reason: str = Field(min_length=5, max_length=1000)


class ScrutinyIn(BaseModel):
    entitlement_basis: str = Field(min_length=5, max_length=500)
    affidavit6_format_ok: bool = True


class ApproveIn(BaseModel):
    certificate_pem: str
    signature_b64: str
    rail: str = "RTGS"


class OverrideIn(BaseModel):
    code: str
    reason: str = Field(min_length=5)


class RejectIn(BaseModel):
    remarks: str = Field(min_length=5)


def _rr(db: Session, p: Principal, rid: str) -> m.ReleaseRequest:
    r = db.get(m.ReleaseRequest, rid)
    if not r:
        raise HTTPException(404, "not found")
    institution_scope(p, r.institution_id)
    return r


def _amount(db: Session, r: m.ReleaseRequest) -> int:
    o = db.get(m.Obligation, r.obligation_id)
    return o.amount_paise if o else 0


@router.get("/release-requests")
def list_releases(p: Principal = Depends(current), db: Session = Depends(get_db), stage: str = "", page: int = 1, size: int = 50):
    q = select(m.ReleaseRequest, m.Institution).join(m.Institution).order_by(m.ReleaseRequest.updated_on.desc())
    if p.user.role == "INSTITUTION":
        q = q.where(m.ReleaseRequest.institution_id == p.user.institution_id)
    if stage == "open":
        q = q.where(m.ReleaseRequest.stage.in_(rel.OPEN_STAGES))
    elif stage:
        q = q.where(m.ReleaseRequest.stage == stage)
    rows = db.execute(q).all()
    by = dict(db.execute(select(m.ReleaseRequest.stage, func.count()).where(
        *( [m.ReleaseRequest.institution_id == p.user.institution_id] if p.user.role == "INSTITUTION" else [])).group_by(m.ReleaseRequest.stage)).all())
    return {"total": len(rows), "by_stage": by, "items": [S.release(r, i, _amount(db, r)) for r, i in rows[(page - 1) * size: page * size]]}


@router.post("/release-requests")
def create_release(body: ReleaseIn, p: Principal = Depends(require("INSTITUTION")), db: Session = Depends(get_db)):
    if body.fdr_id:
        f = db.get(m.Fdr, body.fdr_id)
        if not f:
            raise HTTPException(404, "not found")
        institution_scope(p, f.institution_id)
        if f.status != "verified":
            raise HTTPException(409, {"error": "StateError", "message": "only a verified FDR can be released"})
        oid, fid = f.obligation_id, f.id
    elif body.obligation_id:
        o = db.get(m.Obligation, body.obligation_id)
        if not o:
            raise HTTPException(404, "not found")
        institution_scope(p, o.institution_id)
        oid, fid = o.obligation_id, None
    else:
        raise HTTPException(422, "fdr_id or obligation_id required")
    r = rel.create(db, obligation_id=oid, fdr_id=fid, inst_id=p.user.institution_id, reason=body.reason, actor=p.actor)
    return S.release(r)


@router.get("/release-requests/{rid}")
def get_release(rid: str, p: Principal = Depends(current), db: Session = Depends(get_db)):
    r = _rr(db, p, rid)
    out = S.release(r, db.get(m.Institution, r.institution_id), _amount(db, r))
    k = LEDGER.kernel()
    if r.case_id in k.refunds:
        out["refund"] = _refund(k, r.case_id)
    if r.case_id in k.nocs:
        out["noc"] = k.nocs[r.case_id]
    if p.user.role != "INSTITUTION":
        out["gate"] = rel.gate(r, p.actor) if r.stage in ("SUBMITTED", "SCRUTINY_DONE") else None
    return out


@router.post("/release-requests/{rid}/scrutiny")
def scrutiny(rid: str, body: ScrutinyIn, p: Principal = Depends(require_kernel_role("section_officer")), db: Session = Depends(get_db)):
    return S.release(rel.scrutiny(db, _rr(db, p, rid), p.actor, body.entitlement_basis, body.affidavit6_format_ok))


@router.get("/release-requests/{rid}/gate")
def gate(rid: str, p: Principal = Depends(OFFICIAL), db: Session = Depends(get_db)):
    return rel.gate(_rr(db, p, rid), p.actor)


@router.post("/release-requests/{rid}/approve")
def approve(rid: str, body: ApproveIn, p: Principal = Depends(OFFICIAL), db: Session = Depends(get_db)):
    return rel.approve(db, _rr(db, p, rid), p.user, body.certificate_pem, body.signature_b64, body.rail)


@router.post("/release-requests/{rid}/override")
def override(rid: str, body: OverrideIn, p: Principal = Depends(OFFICIAL), db: Session = Depends(get_db)):
    rel.override(db, _rr(db, p, rid), p.actor, body.code, body.reason)
    return {"ok": True}


@router.post("/release-requests/{rid}/reject")
def reject(rid: str, body: RejectIn, p: Principal = Depends(OFFICIAL), db: Session = Depends(get_db)):
    return S.release(rel.reject(db, _rr(db, p, rid), p.actor, body.remarks))


@router.post("/release-requests/{rid}/lien-discharge")
def lien_discharge(rid: str, p: Principal = Depends(OFFICIAL), db: Session = Depends(get_db)):
    """Asks the issuing bank (SIMULATED) to discharge the lien named in the NOC."""
    return rel.lien_discharge(db, _rr(db, p, rid))


# ------------------------------------------------------------------ payments
def _refund(k, rid: str) -> dict:
    r = k.refunds[rid]
    return {"refund_id": rid, "obligation_id": r["obligation_id"], "institution_id": r["inst_id"], "amount_paise": r["amount"], "rail": r["rail"],
            "state": r["state"], "approver": r["approver"], "status_text": k.refund_status_text(rid), "reissue_target": r.get("reissue_target"),
            "history": [{"at": a, "state": s, "utr": u} for a, s, u in r["history"]],
            "attempts": [{k2: v for k2, v in a.items()} for a in r["attempts"]], "liability": k.liability_register(r["obligation_id"]),
            "payee_verified": k.payee_verified(r["inst_id"]), "simulated_bank": True}


@router.get("/payments")
def payments(p: Principal = Depends(current), db: Session = Depends(get_db)):
    k = LEDGER.kernel()
    items = [_refund(k, rid) for rid in k.refunds if p.user.role != "INSTITUTION" or k.refunds[rid]["inst_id"] == p.user.institution_id]
    names = {i.id: i.name for i in db.scalars(select(m.Institution).where(m.Institution.id.in_([x["institution_id"] for x in items])))}
    for x in items:
        x["institution_name"] = names.get(x["institution_id"])
    items.sort(key=lambda x: x["history"][-1]["at"], reverse=True)
    return {"items": items}


@router.get("/payments/{rid}")
def payment(rid: str, p: Principal = Depends(current)):
    k = LEDGER.kernel()
    if rid not in k.refunds:
        raise HTTPException(404, "not found")
    institution_scope(p, k.refunds[rid]["inst_id"])
    return _refund(k, rid)


@router.post("/payments/{rid}/initiate")
def initiate(rid: str, p: Principal = Depends(require_kernel_role("finance_officer")), db: Session = Depends(get_db)):
    rel.initiate(db, rid, p.actor)
    return _refund(LEDGER.kernel(), rid)


@router.post("/payments/{rid}/reissue")
def reissue(rid: str, p: Principal = Depends(require_kernel_role("finance_officer")), db: Session = Depends(get_db)):
    if LEDGER.kernel().refunds.get(rid, {}).get("state") != "REISSUE_REQUIRED":
        raise HTTPException(409, {"error": "StateError", "message": "re-issue is only possible after a return"})
    rel.initiate(db, rid, p.actor)
    return _refund(LEDGER.kernel(), rid)


class PayeeIn(BaseModel):
    account: str = Field(min_length=6, max_length=30)
    ifsc: str = Field(pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$")
    name: str = Field(min_length=3, max_length=200)
    affidavit9: bool = False


@router.get("/payees/{inst_id}")
def get_payee(inst_id: str, p: Principal = Depends(current)):
    institution_scope(p, inst_id)
    k = LEDGER.kernel()
    pay = k.payees.get(inst_id)
    if not pay:
        return {"payee": None}
    return {"payee": {"account_masked": "••••" + pay["account"][-4:], "ifsc": pay["ifsc"], "name": pay["name"], "verified": k.payee_verified(inst_id)}}


@router.post("/payees/{inst_id}")
def set_payee(inst_id: str, body: PayeeIn, p: Principal = Depends(require("INSTITUTION")), db: Session = Depends(get_db)):
    institution_scope(p, inst_id)
    rel.register_payee(db, inst_id, body.account, body.ifsc, body.name, p.actor, body.affidavit9)
    return get_payee(inst_id, p)


@router.post("/payees/{inst_id}/name-lookup")
def payee_lookup(inst_id: str, p: Principal = Depends(require_kernel_role("finance_officer", "finance_reconciliation_officer")), db: Session = Depends(get_db)):
    return rel.name_lookup(db, inst_id)


# ------------------------------------------------------------------ holds
class HoldIn(BaseModel):
    allocations: list[str] = []
    credits: list[str] = []
    instruments: list[str] = []
    basis: str = Field(min_length=5)


@router.get("/holds")
def holds(p: Principal = Depends(require("AICTE_OFFICIAL", "AUDITOR"))):
    k = LEDGER.kernel()
    now = now_iso()
    return {"items": [{**h, "escalated": h["status"] == "ACTIVE" and now >= h["review_due"]} for h in k.holds.values()],
            "policy": k.policy["holds"]}


@router.post("/holds")
def place_hold(body: HoldIn, p: Principal = Depends(require_kernel_role("finance_reconciliation_officer", "internal_audit")), db: Session = Depends(get_db)):
    scope = {k: v for k, v in (("allocations", body.allocations), ("credits", body.credits), ("instruments", body.instruments)) if v}
    if not scope:
        raise HTTPException(422, "name at least one allocation, credit or instrument")
    import uuid
    hid = f"HOLD-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
    try:
        LEDGER.run(db, lambda k: k.place_hold(hid, scope, body.basis, now_iso(), p.actor))
    except Exception as e:  # noqa: BLE001
        raise domain_http(e) from e
    return LEDGER.kernel().holds[hid]


@router.post("/holds/{hid}/release")
def release_hold(hid: str, body: RejectIn, p: Principal = Depends(require("AICTE_OFFICIAL", "AUDITOR")), db: Session = Depends(get_db)):
    try:
        LEDGER.run(db, lambda k: k.release_hold(hid, now_iso(), p.actor, body.remarks))
    except Exception as e:  # noqa: BLE001
        raise domain_http(e) from e
    return LEDGER.kernel().holds[hid]


@router.post("/holds/review")
def hold_review(p: Principal = Depends(require("AICTE_OFFICIAL", "AUDITOR")), db: Session = Depends(get_db)):
    """Runs the time-driven controls now: overdue credit confirmations, 30-day hold escalation."""
    LEDGER.run(db, lambda k: k.tick(now_iso()))
    return {"ok": True}


# ------------------------------------------------------------------ rules, amounts, policy
@router.get("/rules")
def rules(p: Principal = Depends(current)):
    k = LEDGER.kernel()
    packs = [{"edition_id": e, "title": pk["title"], "effective_from": pk["effective_from"], "effective_to": pk["effective_to"],
              "source_status": pk["source_status"], "confirmed_by_legal_cell": e in k.rules.confirmed, "rules": pk["rules"],
              "note": pk.get("source_note")} for e, pk in k.rules.packs.items()]
    return {"packs": packs, "rulings": [{"case_id": c, "key": key, "on_date": d, **v} for (c, key, d), v in k.rules.rulings.items()]}


@router.get("/rules/resolve")
def resolve(key: str, on_date: date, case_id: str | None = None, p: Principal = Depends(current)):
    r = LEDGER.kernel().rules.resolve(key, on_date.isoformat(), case_id)
    return {"key": r.key, "on_date": r.on_date, "status": r.status, "value": r.value, "cites": r.cites, "editions": r.editions, "usable": r.usable,
            "action": "apply" if r.usable else ("escalate to legal cell" if r.status != "NOT_SPECIFIED" or r.editions else "blocked: no edition covers this date")}


class ConfirmIn(BaseModel):
    reference: str = Field(min_length=3)


@router.post("/rules/{edition}/confirm")
def confirm_pack(edition: str, body: ConfirmIn, p: Principal = Depends(require_kernel_role("legal_cell")), db: Session = Depends(get_db)):
    try:
        LEDGER.run(db, lambda k: k.confirm_rule_pack(edition, now_iso(), p.actor, body.reference))
    except Exception as e:  # noqa: BLE001
        raise domain_http(e) from e
    return {"ok": True}


class RulingIn(BaseModel):
    case_id: str
    key: str
    on_date: date
    value: str
    reference: str


@router.post("/rules/rulings")
def ruling(body: RulingIn, p: Principal = Depends(require_kernel_role("legal_cell")), db: Session = Depends(get_db)):
    try:
        LEDGER.run(db, lambda k: k.legal_ruling(body.case_id, body.key, body.on_date.isoformat(), body.value, body.reference, now_iso(), p.actor))
    except Exception as e:  # noqa: BLE001
        raise domain_http(e) from e
    return {"ok": True}


class DepositIn(BaseModel):
    lines: list[dict]
    institution_type: str
    leased: bool = False


@router.post("/rules/table-1-4")
def table_1_4(body: DepositIn, p: Principal = Depends(current)):
    return required_deposit(body.lines, body.institution_type, body.leased)


class PenaltyIn(BaseModel):
    principal_paise: int = Field(gt=0)
    clause: str


@router.post("/rules/penalty-proposal")
def penalty(body: PenaltyIn, p: Principal = Depends(OFFICIAL)):
    return penalty_proposal(body.principal_paise, body.clause)


def _active_policy(db: Session) -> dict:
    row = db.scalars(select(m.PolicyVersion).order_by(m.PolicyVersion.id.desc()).limit(1)).first()
    return row.policy if row else LEDGER.policy


@router.get("/policy/changes")
def policy_changes(p: Principal = Depends(current), db: Session = Depends(get_db)):
    """Every policy change from the portal hash chain (both the release policy and the notification policy), newest first,
    with each changed value before and after."""
    rows = db.scalars(select(m.PortalEvent).where(m.PortalEvent.type.in_(("policy_changed", "notify_policy_changed")))
                      .order_by(m.PortalEvent.seq.desc()).limit(100)).all()
    out = []
    for e in rows:
        d = json.loads(e.data)
        out.append({"seq": e.seq, "hash": e.hash, "at": e.at, "actor": e.actor, "policy": "release" if e.type == "policy_changed" else "notification",
                    "version": d.get("version"), "reason": d.get("reason"), "changes": d.get("changes"),
                    "sections": d.get("sections")})
    return {"items": out}


@router.get("/policy")
def get_policy(p: Principal = Depends(current), db: Session = Depends(get_db)):
    rows = db.scalars(select(m.PolicyVersion).order_by(m.PolicyVersion.id.desc())).all()
    return {"active": rows[0].policy if rows else LEDGER.policy,
            "editable": p.user.role == "AICTE_OFFICIAL" and p.user.kernel_role in ("director", "deputy_director"),
            "versions": [{"id": r.id, "created_at": r.created_at.isoformat(timespec="seconds"), "created_by": r.created_by, "reason": r.reason} for r in rows]}


class PolicyIn(BaseModel):
    policy: dict
    reason: str = Field(min_length=10)


@router.put("/policy")
def put_policy(body: PolicyIn, p: Principal = Depends(require_kernel_role("director", "deputy_director")), db: Session = Depends(get_db)):
    """Policy changes need an AICTE approving role. New versions apply to future commands; history is kept."""
    if p.user.role != "AICTE_OFFICIAL":
        raise HTTPException(403, "your role cannot do this")
    required = {"release", "holds", "payments", "roles", "admin_checks"}
    if not required <= set(body.policy):
        raise HTTPException(422, f"policy must contain {sorted(required)}")
    old = _active_policy(db)
    diff = portal_audit.changes(old, body.policy)
    if not diff:
        raise HTTPException(409, "the new policy is the same as the current one")
    retyped = [d["path"] for d in diff if d["before"] is not None and d["after"] is not None and type(d["before"]) is not type(d["after"])]
    if retyped:
        raise HTTPException(422, f"a value must keep its type: {', '.join(retyped)}")
    negative = [d["path"] for d in diff if isinstance(d["after"], (int, float)) and not isinstance(d["after"], bool) and d["after"] <= 0]
    if negative:
        raise HTTPException(422, f"numbers must be positive: {', '.join(negative)}")
    row = m.PolicyVersion(created_at=datetime.now(), created_by=p.actor, reason=body.reason, policy=body.policy)
    db.add(row)
    db.flush()
    portal_audit.record(db, "policy_changed", p.actor, {"version": row.id, "reason": body.reason, "changes": diff, "policy": body.policy})
    db.commit()
    LEDGER.rebuild()
    return get_policy(p, db)


# ------------------------------------------------------------------ reconciliation & bank views
@router.get("/reconciliation")
def reconciliation(p: Principal = Depends(require("AICTE_OFFICIAL", "AUDITOR")), db: Session = Depends(get_db)):
    k = LEDGER.kernel()
    cert = k.certification_report()
    per_bank = []
    for code, name in BANKS.items():
        fs = db.scalars(select(m.Fdr).where(m.Fdr.bank == code, m.Fdr.status.in_(("verified", "pending", "discrepancy")))).all()
        conf = sum(1 for f in fs if f.instrument_id in k.instruments and any(k.evidence_valid(c["evidence_id"]) for c in k.instruments[f.instrument_id]["confirmations"]))
        per_bank.append({"bank": code, "bank_name": name, "live": len(fs), "confirmed": conf, "mismatch": sum(1 for f in fs if f.status == "discrepancy"),
                         "awaiting": len(fs) - conf, "channel": "SIMULATED API"})
    signers = [{"key_id": s.key_id, "bank": s.bank, "valid_from": s.valid_from, "ended_at": s.ended_at, "compromised_from": s.compromised_from, "note": s.note}
               for s in db.scalars(select(m.BankSigner).order_by(m.BankSigner.key_id))]
    return {"certification": cert, "per_bank": per_bank, "signers": signers, "confirmation_requests": k.confirmation_requests(), "simulated": True}


@router.get("/bank/messages")
def bank_messages(p: Principal = Depends(require("AICTE_OFFICIAL", "AUDITOR")), db: Session = Depends(get_db), kind: str = "", status: str = "",
                  ref: str = "", page: int = 1, size: int = 25):
    q = select(m.BankMessage).order_by(m.BankMessage.id.desc())
    for col, v in ((m.BankMessage.kind, kind), (m.BankMessage.status, status), (m.BankMessage.ref, ref)):
        if v:
            q = q.where(col == v)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.offset((page - 1) * size).limit(size)).all()
    return {"total": total, "simulated": True, "items": [S.bank_message(b) for b in rows]}


@router.get("/bank/signers")
def bank_signers(p: Principal = Depends(require("AICTE_OFFICIAL", "AUDITOR")), db: Session = Depends(get_db)):
    return reconciliation(p, db)["signers"]


# ------------------------------------------------------------------ reports
@router.get("/reports/summary")
def report_summary(p: Principal = Depends(require("AICTE_OFFICIAL", "AUDITOR")), db: Session = Depends(get_db)):
    from .data import _compliance, _stats
    today = date.today()
    months = []
    for i in range(11, -1, -1):
        start = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        sub = db.scalar(select(func.count()).select_from(m.Fdr).where(m.Fdr.submitted_on >= start, m.Fdr.submitted_on < end))
        months.append({"month": start.strftime("%b %y"), "submitted": sub})
    fwd = []
    for i in range(12):
        start = (today.replace(day=1) + timedelta(days=32 * i)).replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        fwd.append({"month": start.strftime("%b %y"), "count": db.scalar(select(func.count()).select_from(m.Fdr).where(
            m.Fdr.status == "verified", m.Fdr.maturity_date >= start, m.Fdr.maturity_date < end))})
    banks = [{"bank": b, "bank_name": BANKS[b], "amount_paise": int(a)} for b, a in db.execute(
        select(m.Fdr.bank, func.sum(m.Fdr.amount_paise)).where(m.Fdr.status.in_(("verified", "pending", "discrepancy"))).group_by(m.Fdr.bank))]
    states = [{"state": s, "count": c} for s, c in db.execute(select(m.Institution.state, func.count()).join(m.Fdr).where(
        m.Fdr.status.in_(("verified", "pending", "discrepancy"))).group_by(m.Institution.state).order_by(func.count().desc()).limit(10))]
    # verification turnaround, measured from stored timestamps: submission -> first accepted bank confirmation
    tat = []
    for f, received in db.execute(select(m.Fdr, func.min(m.BankMessage.received_at)).join(m.BankMessage, m.BankMessage.ref == m.Fdr.id)
                                  .where(m.BankMessage.kind == "instrument_confirmation", m.BankMessage.status == "ACCEPTED").group_by(m.Fdr.id)):
        tat.append((datetime.fromisoformat(received) - f.submitted_on).total_seconds() / 86400)
    return {"stats": _stats(db), "compliance": _compliance(db), "submissions_by_month": months, "maturity_forecast": fwd,
            "value_by_bank": sorted(banks, key=lambda x: -x["amount_paise"]), "top_states": states,
            "avg_days_to_bank_confirmation": round(sum(tat) / len(tat), 2) if tat else None, "confirmation_samples": len(tat),
            "note": "Computed from the seeded demo database. Not AICTE data."}


@router.get("/reports/export.csv")
def export_csv(kind: str = Query("fdrs", pattern="^(fdrs|institutions|audit|bank_messages)$"), p: Principal = Depends(require("AICTE_OFFICIAL", "AUDITOR")),
               db: Session = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf)
    if kind == "fdrs":
        w.writerow(["FDR", "Institution", "AICTE ID", "State", "Bank", "Instrument no.", "Amount (Rs)", "Issue", "Maturity", "Status", "Bucket"])
        for f, i in db.execute(select(m.Fdr, m.Institution).join(m.Institution).order_by(m.Fdr.id)):
            w.writerow([f.id, i.name, i.aicte_id, i.state, BANKS[f.bank], f.instrument_no, f.amount_paise // 100, f.issue_date, f.maturity_date, f.status, S.bucket(f)])
    elif kind == "institutions":
        w.writerow(["ID", "AICTE ID", "Name", "Type", "City", "State"])
        for i in db.scalars(select(m.Institution).order_by(m.Institution.id)):
            w.writerow([i.id, i.aicte_id, i.name, i.type, i.city, i.state])
    elif kind == "audit":
        w.writerow(["chain", "seq", "at", "actor", "type", "prev", "hash"])
        for e in db.scalars(select(m.KernelEvent).order_by(m.KernelEvent.seq)):
            w.writerow(["kernel", e.seq, e.at, e.actor, e.type, e.prev, e.hash])
        for e in db.scalars(select(m.PortalEvent).order_by(m.PortalEvent.seq)):
            w.writerow(["portal", e.seq, e.at, e.actor, e.type, e.prev, e.hash])
    else:
        w.writerow(["id", "received_at", "kind", "bank", "key_id", "status", "reason", "simulated"])
        for b in db.scalars(select(m.BankMessage).order_by(m.BankMessage.id)):
            w.writerow([b.id, b.received_at, b.kind, b.bank, b.key_id, b.status, b.reason or "", "SIMULATED" if b.simulated else ""])
    data = "﻿" + buf.getvalue()
    return StreamingResponse(iter([data]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="trust-ledger-{kind}-{date.today()}.csv"'})


# ------------------------------------------------------------------ audit trail
@router.get("/audit-trail")
def audit_trail(p: Principal = Depends(require("AICTE_OFFICIAL", "AUDITOR")), db: Session = Depends(get_db), chain: str = "kernel", q: str = "",
                page: int = 1, size: int = 20):
    model = m.KernelEvent if chain == "kernel" else m.PortalEvent
    stmt = select(model).order_by(model.seq.desc())
    if q:
        like = f"%{q}%"
        stmt = stmt.where((model.data.like(like)) | (model.actor.like(like)) | (model.type.like(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.offset((page - 1) * size).limit(size)).all()
    return {"chain": chain, "total": total, "items": [{"seq": r.seq, "at": r.at, "type": r.type, "actor": r.actor, "data": mask_pii(event_data(r)),
                                                      "prev": r.prev, "hash": r.hash} for r in rows]}


@router.post("/audit-trail/verify")
def audit_verify(p: Principal = Depends(require("AICTE_OFFICIAL", "AUDITOR")), db: Session = Depends(get_db)):
    kernel_rows = db.scalars(select(m.KernelEvent).order_by(m.KernelEvent.seq)).all()
    portal_rows = db.scalars(select(m.PortalEvent).order_by(m.PortalEvent.seq)).all()
    kv = portal_audit.verify_rows(kernel_rows)
    pv = portal_audit.verify_rows(portal_rows)
    # off-host checkpoint (demo grade): catches deletion of the LAST events, which a chain alone cannot see
    cp_path = Path(get_settings().checkpoint_path).expanduser()
    checkpoint = {"path": str(cp_path), "found": cp_path.exists(), "valid": None, "detail": "no checkpoint file"}
    if cp_path.exists():
        lines = [json.loads(x) for x in cp_path.read_text().splitlines() if x.strip()]
        if lines:
            last = lines[-1]
            row = next((r for r in kernel_rows if r.seq == last["seq"]), None)
            if row is None:
                checkpoint.update(valid=False, detail=f"checkpoint names event {last['seq']}, which is missing from the database (deleted)")
            elif row.hash != last["hash"]:
                checkpoint.update(valid=False, detail=f"event {last['seq']} hash differs from the checkpoint (rewritten)")
            else:
                checkpoint.update(valid=True, detail=f"database contains checkpointed head {last['seq']} ({last['hash'][:12]}…) written {last['written_at']}")
            checkpoint["checkpoint_seq"] = last["seq"]
    replay_ok = None
    if kv["valid"]:
        from trustledger.audit import Event, EventStore
        from trustledger.kernel import Kernel
        st = EventStore()
        for r in kernel_rows:
            st._events.append(Event(r.seq, r.at, r.type, r.actor, event_data(r), r.prev, r.hash))
        replay_ok = Kernel.replay(st, LEDGER.policy, LEDGER.packs).snapshot() == LEDGER.kernel().snapshot()
    ok = kv["valid"] and pv["valid"] and checkpoint["valid"] is not False and replay_ok is not False
    portal_audit.record(db, "audit_verified", p.actor, {"ok": ok, "kernel_events": kv["events"], "portal_events": pv["events"]})
    db.commit()
    return {"ok": ok, "kernel_chain": kv, "portal_chain": pv, "checkpoint": checkpoint, "replay_matches_live_state": replay_ok,
            "limits": "Demo-grade anchoring: a local checkpoint file, not an RFC 3161 time-stamp (planned)."}




# ------------------------------------------------------------------ legacy import
class LegacyIn(BaseModel):
    batch_id: str
    statement_lines: list[dict] = []   # AICTE's own bank statement credits: utr, amount_paise, value_date, remitter_name, remitter_account, narrative
    records: list[dict]                # legacy register rows: legacy_id, inst_id, inst_name, amount_paise, instrument_class, utr | fdr_number, bank


@router.post("/legacy/import")
def legacy_import(body: LegacyIn, p: Principal = Depends(require_kernel_role("finance_reconciliation_officer")), db: Session = Depends(get_db)):
    """AICTE's bank statements first (as SIMULATED signed credit advices from AICTE's banker), then the legacy register.
    The kernel never upgrades confidence, never produces TRACEABLE, flags duplicates and blocks nothing."""
    from ..bank.deliver import deliver
    from ..bank.simulator import FINANCE_BANK, gateway
    lines = []
    for ln in body.statement_lines:
        env = gateway(db).advice.credit_advice(FINANCE_BANK, ln["utr"], ln["amount_paise"], ln["value_date"], ln.get("remitter_name"),
                                               ln.get("remitter_account"), ln.get("narrative", ""))
        lines.append(deliver(db, env, evidence_id=f"E-STMT-{ln['utr']}", ref=body.batch_id))
    recs = [{**{k: v for k, v in r.items() if k != "amount_paise"}, "amount": r["amount_paise"]} for r in body.records]
    try:
        report = LEDGER.run(db, lambda k: k.import_legacy(body.batch_id, recs, now_iso(), actor=f"migration:{p.user.username.split('@')[0]}"))
    except Exception as e:  # noqa: BLE001
        raise domain_http(e) from e
    k = LEDGER.kernel()
    conf = {f"LEG-{r['legacy_id']}": (k.allocation_confidence(f"A-LEG-{r['legacy_id']}") if f"A-LEG-{r['legacy_id']}" in k.allocations else
                                      ("LEGACY_DECLARED" if r["instrument_class"] == "ONLINE" else "FDR: needs just-in-time bank confirmation"))
            for r in body.records}
    return {"statement_lines": lines, "report": report, "confidence": conf}
