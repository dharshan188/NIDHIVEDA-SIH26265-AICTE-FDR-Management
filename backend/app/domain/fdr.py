"""FDR lifecycle on top of the kernel."""
from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..nudge import notify
from .. import models as m
from .. import documents, portal_audit
from ..bank.deliver import deliver
from ..bank.simulator import BANKS, gateway
from ..ledger import LEDGER
from ..projections import bank_view, mismatches, refresh_fdr
from .common import domain_http, now_iso


def next_fdr_id(db: Session, year: int) -> str:
    prefix = f"FDR{year}"
    last = db.scalar(select(func.max(m.Fdr.id)).where(m.Fdr.id.like(f"{prefix}%")))
    n = int(last[len(prefix):]) + 1 if last else 1
    return f"{prefix}{n:05d}"


def submit(db: Session, *, inst_id: str, actor: str, bank: str, branch: str, instrument_no: str, amount_paise: int, rate_bp: int,
           issue: date, maturity: date, docs: list[dict], programme: str = "Security deposit", renewal_of: str | None = None,
           at: str | None = None, fdr_id: str | None = None) -> m.Fdr:
    if bank not in BANKS:
        raise HTTPException(422, "unknown bank")
    if maturity <= issue:
        raise HTTPException(422, "maturity must be after the issue date")
    if db.scalars(select(m.Fdr).where(m.Fdr.bank == bank, m.Fdr.instrument_no == instrument_no)).first():
        raise HTTPException(409, {"error": "Duplicate", "message": "this FDR number is already registered for this bank"})
    at = at or now_iso()
    fid = fdr_id or next_fdr_id(db, issue.year)
    oid, iid = f"OBL-{fid}", f"INS-{fid}"

    def cmd(k):
        k.create_obligation(oid, inst_id, programme, amount_paise, "FDR", at, actor=actor)
        k.register_instrument(iid, oid, instrument_no, bank, amount_paise, issue.isoformat(), maturity.isoformat(), at, actor, source="institution")

    def after(s: Session, k, new) -> None:
        f = m.Fdr(id=fid, institution_id=inst_id, obligation_id=oid, instrument_id=iid, bank=bank, branch=branch, instrument_no=instrument_no,
                  amount_paise=amount_paise, rate_bp=rate_bp, issue_date=issue, maturity_date=maturity,
                  submitted_on=datetime.fromisoformat(at), status="pending", renewal_of=renewal_of)
        s.add(f)
        s.flush()
        for d in docs:
            documents.add_row(s, fid, d, datetime.fromisoformat(at))
        if renewal_of:
            old = s.get(m.Fdr, renewal_of)
            old.renewed_by = fid
        portal_audit.record(s, "fdr_submitted", actor, {"fdr_id": fid, "bank": bank, "instrument_no": instrument_no, "amount": amount_paise,
                                                        "renewal_of": renewal_of, "documents": [d["sha256"] for d in docs]}, at=at)
        inst = s.get(m.Institution, inst_id)
        notify(s, "aicte", "fdr_submitted", {"fdr_id": fid, "institution": inst.name if inst else inst_id, "bank": BANKS[bank]}, ref=fid, at=at,
               institution_id=inst_id)

    try:
        LEDGER.run(db, cmd, after)
    except Exception as e:  # noqa: BLE001
        raise domain_http(e) from e
    return db.get(m.Fdr, fid)


def request_bank_confirmation(db: Session, fdr: m.Fdr, ref_note: str = "") -> dict:
    """Ask the issuing bank (simulated) for its current record of the instrument: just-in-time verification."""
    env = gateway(db).fdr_confirmation.confirm(fdr.bank, fdr.instrument_no)
    n = db.scalar(select(func.count()).select_from(m.BankMessage).where(m.BankMessage.ref == fdr.id)) or 0
    out = deliver(db, env, evidence_id=f"E-IC-{fdr.id}-{n + 1}", ref=fdr.id)
    db.refresh(fdr)
    return out


def comparison(k, fdr: m.Fdr) -> dict:
    """Declared vs bank-confirmed, field by field, with the confidence of each item."""
    bv = bank_view(k, fdr.obligation_id)
    ins, conf = bv["instrument"], bv["confirmation"]
    invalid = bv.get("invalid_confirmations") or []
    rows = []
    declared = {"instrument_no": fdr.instrument_no, "bank": fdr.bank, "amount": fdr.amount_paise,
                "maturity_date": fdr.maturity_date.isoformat(), "status": "ACTIVE", "lien_holder": "AICTE"}
    bank = None
    if conf:
        bank = {"instrument_no": ins["number"], "bank": ins["bank"], "amount": conf["amount"], "maturity_date": conf["maturity_date"][:10],
                "status": conf["status"], "lien_holder": conf["lien_holder"]}
    for field, label in (("instrument_no", "FDR number"), ("bank", "Issuing bank"), ("amount", "Principal"), ("maturity_date", "Maturity date"),
                         ("status", "Status at bank"), ("lien_holder", "Lien in favour of")):
        dv = declared[field]
        bvv = bank[field] if bank else None
        if bank is None:
            conf_level = "UNVERIFIED_SOURCE" if invalid else "DECLARED"
        elif bvv == dv:
            conf_level = "BANK_CONFIRMED"
        else:
            conf_level = "MISMATCH"
        rows.append({"field": field, "label": label, "declared": dv, "bank_confirmed": bvv, "confidence": conf_level})
    ev = k.evidence.get(conf["evidence_id"]) if conf else None
    return {"rows": rows, "simulated": True,
            "confirmation": ({"evidence_id": conf["evidence_id"], "as_of": conf["as_of"], "bank": ev["bank"], "key_id": ev["key_id"],
                              "received_at": ev["received_at"], "signer_valid": True} if conf else None),
            "invalid_confirmations": [{"evidence_id": c["evidence_id"], "key_id": k.evidence[c["evidence_id"]]["key_id"],
                                       "received_at": k.evidence[c["evidence_id"]]["received_at"]} for c in invalid],
            "problems": mismatches(ins, conf) if (ins and conf) else []}


def verify(db: Session, fdr: m.Fdr, actor: str, note: str | None) -> m.Fdr:
    k = LEDGER.kernel()
    bv = bank_view(k, fdr.obligation_id)
    if not bv["confirmation"]:
        raise HTTPException(409, {"error": "NoBankConfirmation", "message": "the issuing bank has not confirmed this instrument; request confirmation first"})
    bad = mismatches(bv["instrument"], bv["confirmation"])
    if bad:
        raise HTTPException(409, {"error": "Mismatch", "message": "bank confirmation does not match the declared instrument", "problems": bad})
    if fdr.discrepancy_reason and not fdr.discrepancy_reason.startswith("Bank:") and not note:
        raise HTTPException(409, {"error": "OpenDiscrepancy", "message": "a recorded discrepancy is open; record how it was resolved"})
    fdr.scrutinised, fdr.scrutiny_note, fdr.discrepancy_reason = True, note, None
    refresh_fdr(db, k, fdr)
    portal_audit.record(db, "fdr_verified", actor, {"fdr_id": fdr.id, "note": note, "relied_evidence": bv["confirmation"]["evidence_id"]})
    notify(db, f"institution:{fdr.institution_id}", "fdr_verified", {"fdr_id": fdr.id}, ref=fdr.id)
    db.commit()
    return fdr


def flag(db: Session, fdr: m.Fdr, actor: str, reason: str) -> m.Fdr:
    fdr.discrepancy_reason, fdr.status, fdr.scrutinised = reason, "discrepancy", False
    portal_audit.record(db, "fdr_discrepancy_flagged", actor, {"fdr_id": fdr.id, "reason": reason})
    notify(db, f"institution:{fdr.institution_id}", "clarification_required", {"fdr_id": fdr.id, "reason": reason}, ref=fdr.id)
    db.commit()
    return fdr


def renewal_decision(db: Session, fdr: m.Fdr, actor: str, new_number: str, new_maturity: date) -> str:
    today = date.today().isoformat()
    try:
        return LEDGER.run(db, lambda k: k.request_renewal(fdr.instrument_id, today, new_number, new_maturity.isoformat(), now_iso(), actor))
    except Exception as e:  # noqa: BLE001
        raise domain_http(e) from e
