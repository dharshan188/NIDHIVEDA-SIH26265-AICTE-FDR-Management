"""Release of a security deposit: FDR -> NOC -> lien discharge; ONLINE -> sanction (refund) -> payment."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..nudge import notify
from .. import models as m
from .. import portal_audit
from ..bank.deliver import deliver
from ..bank.simulator import gateway
from ..ledger import LEDGER
from ..security import DscError, verify_dsc
from .common import domain_http, now_iso

OPEN_STAGES = ("SUBMITTED", "SCRUTINY_DONE", "APPROVED")


def next_id(db: Session) -> str:
    n = (db.scalar(select(func.count()).select_from(m.ReleaseRequest)) or 0) + 1
    while db.get(m.ReleaseRequest, f"REL{datetime.now().year}{n:05d}"):
        n += 1
    return f"REL{datetime.now().year}{n:05d}"


def create(db: Session, *, obligation_id: str, fdr_id: str | None, inst_id: str, reason: str, actor: str) -> m.ReleaseRequest:
    live = db.scalars(select(m.ReleaseRequest).where(m.ReleaseRequest.obligation_id == obligation_id, m.ReleaseRequest.stage.in_(OPEN_STAGES))).first()
    if live:
        raise HTTPException(409, {"error": "Duplicate", "message": f"release request {live.id} is already open for this deposit"})
    now = datetime.now()
    rr = m.ReleaseRequest(id=next_id(db), obligation_id=obligation_id, fdr_id=fdr_id, institution_id=inst_id, reason=reason, stage="SUBMITTED",
                          raised_by=actor, raised_on=now, updated_on=now)
    db.add(rr)
    portal_audit.record(db, "release_requested", actor, {"release_id": rr.id, "obligation_id": obligation_id, "reason": reason})
    inst = db.get(m.Institution, inst_id)
    notify(db, "aicte", "release_requested", {"request_id": rr.id, "institution": inst.name if inst else inst_id}, ref=rr.id, institution_id=inst_id)
    db.commit()
    return rr


def scrutiny(db: Session, rr: m.ReleaseRequest, actor: str, entitlement_basis: str, affidavit_format_ok: bool) -> m.ReleaseRequest:
    if rr.stage != "SUBMITTED":
        raise HTTPException(409, {"error": "StateError", "message": f"request is {rr.stage}"})
    at = now_iso()

    def cmd(k):
        k.record_entitlement(rr.obligation_id, entitlement_basis, at, actor)
        k.record_affidavit(rr.obligation_id, "AFFIDAVIT-6", affidavit_format_ok, at, actor)

    def after(s: Session, k, new):
        r = s.get(m.ReleaseRequest, rr.id)
        r.stage, r.scrutiny_by, r.updated_on = "SCRUTINY_DONE", actor, datetime.now()
        portal_audit.record(s, "release_scrutiny_done", actor, {"release_id": rr.id, "entitlement": entitlement_basis})

    try:
        LEDGER.run(db, cmd, after)
    except Exception as e:  # noqa: BLE001
        raise domain_http(e) from e
    # just-in-time evidence: fresh bank confirmation of the current instrument
    if rr.fdr_id:
        from .fdr import request_bank_confirmation
        request_bank_confirmation(db, db.get(m.Fdr, rr.fdr_id))
    db.refresh(rr)
    return rr


def gate(rr: m.ReleaseRequest, approver_actor: str) -> dict:
    k = LEDGER.kernel()
    dec = k.evaluate_release(rr.obligation_id, now_iso(), approver_actor)
    out = dec.as_dict()
    out["allowed"] = dec.allowed
    out["blocked_by"] = dec.blocked_by
    out["approval_message"] = approval_message(rr, out)
    return out


def approval_message(rr: m.ReleaseRequest, decision: dict) -> str:
    """What the approver signs with their DSC: the request and a digest of the gate decision they saw."""
    digest = hashlib.sha256(json.dumps({c["code"]: c["ok"] for c in decision["checks"]}, sort_keys=True).encode()).hexdigest()[:32]
    return f"TL-APPROVE:{rr.id}:{rr.obligation_id}:{digest}"


def approve(db: Session, rr: m.ReleaseRequest, user: m.User, certificate_pem: str, signature_b64: str, rail: str = "RTGS") -> dict:
    if rr.stage != "SCRUTINY_DONE":
        raise HTTPException(409, {"error": "StateError", "message": f"request is {rr.stage}; scrutiny must be completed first"})
    if rr.scrutiny_by == user.actor:
        raise HTTPException(409, {"error": "MakerChecker", "message": "the officer who did the scrutiny cannot approve it"})
    preview = gate(rr, user.actor)
    try:
        serial = verify_dsc(certificate_pem, signature_b64, preview["approval_message"])
    except DscError as e:
        raise HTTPException(401, {"error": "DSC", "message": str(e)}) from e
    if serial != user.dsc_serial:
        raise HTTPException(401, {"error": "DSC", "message": "certificate is not registered to the approver"})
    case_id = f"{'NOC' if rr.fdr_id else 'RF'}-{rr.id}"
    at = now_iso()

    def after(s: Session, k, new):
        r = s.get(m.ReleaseRequest, rr.id)
        r.stage, r.approved_by, r.case_id, r.dsc_serial, r.dsc_signature, r.updated_on = "APPROVED", user.actor, case_id, serial, signature_b64, datetime.now()
        portal_audit.record(s, "release_approved", user.actor, {"release_id": rr.id, "case_id": case_id, "dsc_serial": serial})
        notify(s, f"institution:{rr.institution_id}", "release_approved", {
            "request_id": rr.id,
            "what": {"en": "NOC issued", "hi": "एनओसी जारी"} if rr.fdr_id else {"en": "refund sanctioned", "hi": "रिफ़ंड स्वीकृत"},
            "until": ({"en": "the bank confirms lien discharge", "hi": "बैंक ग्रहणाधिकार मुक्ति की पुष्टि न करे"} if rr.fdr_id
                      else {"en": "your bank confirms the credit", "hi": "आपका बैंक जमा की पुष्टि न करे"})}, ref=rr.id, at=at)

    try:
        dec = LEDGER.run(db, lambda k: k.authorise_release(case_id, rr.obligation_id, at, user.actor, rail=rail), after)
    except Exception as e:  # noqa: BLE001
        raise domain_http(e) from e
    return {"case_id": case_id, "decision": dec.as_dict()}


def override(db: Session, rr: m.ReleaseRequest, actor: str, code: str, reason: str) -> None:
    def after(s: Session, k, new):
        portal_audit.record(s, "admin_override", actor, {"release_id": rr.id, "code": code, "reason": reason})

    try:
        LEDGER.run(db, lambda k: k.override_admin(rr.obligation_id, code, now_iso(), actor, reason), after)
    except Exception as e:  # noqa: BLE001
        raise domain_http(e) from e


def reject(db: Session, rr: m.ReleaseRequest, actor: str, remarks: str) -> m.ReleaseRequest:
    if rr.stage not in ("SUBMITTED", "SCRUTINY_DONE"):
        raise HTTPException(409, {"error": "StateError", "message": f"request is {rr.stage}"})
    rr.stage, rr.remarks, rr.updated_on = "REJECTED", remarks, datetime.now()
    portal_audit.record(db, "release_rejected", actor, {"release_id": rr.id, "remarks": remarks})
    notify(db, f"institution:{rr.institution_id}", "release_rejected", {"request_id": rr.id, "reason": remarks}, ref=rr.id)
    db.commit()
    return rr


def lien_discharge(db: Session, rr: m.ReleaseRequest) -> dict:
    """The issuing bank (simulated) discharges the lien named in the NOC; completion is only on that confirmation."""
    fdr = db.get(m.Fdr, rr.fdr_id)
    noc = LEDGER.kernel().nocs.get(rr.case_id or "")
    if not noc:
        raise HTTPException(409, {"error": "StateError", "message": "no NOC issued"})
    env = gateway(db).lien_discharge.discharge(fdr.bank, noc["instrument_no"])
    out = deliver(db, env, evidence_id=f"E-LD-{rr.id}", ref=fdr.id)
    if out["status"] == "ACCEPTED":
        r = db.get(m.ReleaseRequest, rr.id)
        r.stage, r.updated_on = "COMPLETED", datetime.now()
        db.commit()
    return out


# ------------------------------------------------------------------ payments
def initiate(db: Session, refund_id: str, actor: str) -> None:
    def after(s, k, new):
        portal_audit.record(s, "payment_initiated", actor, {"refund_id": refund_id})

    try:
        LEDGER.run(db, lambda k: k.initiate_payment(refund_id, now_iso(), actor), after)
    except Exception as e:  # noqa: BLE001
        raise domain_http(e) from e


def _utr(db: Session) -> str:
    n = (db.scalar(select(func.count()).select_from(m.PaymentAttempt)) or 0) + 1
    return f"SBINR5{datetime.now():%Y%m%d}{n:06d}"


def bank_debit(db: Session, refund_id: str) -> dict:
    k = LEDGER.kernel()
    r = k.refunds[refund_id]
    pay = k.payees[r["inst_id"]]
    env = gateway(db).advice.debit_advice(refund_id, _utr(db), r["amount"], pay["account"], pay["ifsc"])
    return deliver(db, env, ref=refund_id)


def bank_confirm(db: Session, refund_id: str, *, amount: int | None = None, account: str | None = None) -> dict:
    k = LEDGER.kernel()
    att = k.refunds[refund_id]["attempts"][-1]
    env = gateway(db).credit_confirmation.confirm(att["utr"], amount or att["amount"], account or att["beneficiary_account"], now_iso())
    out = deliver(db, env, ref=refund_id)
    # completion follows the bank's positive credit confirmation, never the debit
    if LEDGER.kernel().refunds[refund_id]["state"] == "SETTLED":
        rr = db.scalars(select(m.ReleaseRequest).where(m.ReleaseRequest.case_id == refund_id)).first()
        if rr and rr.stage == "APPROVED":
            rr.stage, rr.updated_on = "COMPLETED", datetime.now()
            portal_audit.record(db, "release_completed", "system:payments", {"release_id": rr.id, "refund_id": refund_id})
            db.commit()
    return out


def bank_return(db: Session, refund_id: str, reason_code: str) -> dict:
    k = LEDGER.kernel()
    att = k.refunds[refund_id]["attempts"][-1]
    env = gateway(db).return_advice.return_payment(att["utr"], _utr(db).replace("SBINR5", "SBINRR"), att["amount"], reason_code)
    return deliver(db, env, ref=refund_id)


def register_payee(db: Session, inst_id: str, account: str, ifsc: str, name: str, actor: str, affidavit9: bool = False) -> None:
    basis = {"affidavit": "AFFIDAVIT-9", "ter_fee_paid": True} if affidavit9 else None

    def after(s, k, new):
        portal_audit.record(s, "payee_registered", actor, {"inst_id": inst_id, "account_last4": account[-4:], "ifsc": ifsc, "affidavit9": affidavit9})

    try:
        LEDGER.run(db, lambda k: k.register_payee(inst_id, account, ifsc, name, now_iso(), actor, change_basis=basis), after)
    except Exception as e:  # noqa: BLE001
        raise domain_http(e) from e


def name_lookup(db: Session, inst_id: str) -> dict:
    pay = LEDGER.kernel().payees.get(inst_id)
    if not pay:
        raise HTTPException(409, {"error": "StateError", "message": "no payee registered"})
    env = gateway(db).name_lookup.lookup(pay["account"], pay["ifsc"])
    out = deliver(db, env, ref=inst_id)
    out["verified"] = LEDGER.kernel().payee_verified(inst_id)
    out["name_at_bank"] = env["payload"]["name_at_bank"]
    return out


