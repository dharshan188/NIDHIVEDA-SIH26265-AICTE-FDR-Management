from __future__ import annotations

from datetime import date

from .crypto import mask, mask_pii, open_pii
from . import models as m
from .bank.simulator import BANKS


def bucket(f: m.Fdr, today: date | None = None) -> str:
    today = today or date.today()
    if f.status == "verified":
        return "maturing" if (f.maturity_date - today).days <= 90 else "active"
    return f.status


def fdr(f: m.Fdr, inst: m.Institution | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    return {
        "id": f.id, "institution_id": f.institution_id, "institution_name": inst.name if inst else None,
        "bank": f.bank, "bank_name": BANKS.get(f.bank, f.bank), "branch": f.branch, "instrument_no": f.instrument_no,
        "amount_paise": f.amount_paise, "rate_bp": f.rate_bp, "issue_date": f.issue_date.isoformat(), "maturity_date": f.maturity_date.isoformat(),
        "submitted_on": f.submitted_on.isoformat(timespec="seconds"), "status": f.status, "bucket": bucket(f, today),
        "days_left": (f.maturity_date - today).days, "discrepancy_reason": f.discrepancy_reason, "scrutinised": f.scrutinised,
        "renewal_of": f.renewal_of, "renewed_by": f.renewed_by, "closed_reason": f.closed_reason,
    }


def institution(i: m.Institution) -> dict:
    return {"id": i.id, "aicte_id": i.aicte_id, "name": i.name, "type": i.type, "state": i.state, "city": i.city, "email": i.email,
            "phone": i.phone, "principal": i.principal, "established": i.established, "intake": i.intake,
            "pan_masked": mask(i.pan), "registered_mobile_masked": mask(i.registered_mobile)}


def release(r: m.ReleaseRequest, inst: m.Institution | None = None, amount: int | None = None) -> dict:
    return {"id": r.id, "obligation_id": r.obligation_id, "fdr_id": r.fdr_id, "institution_id": r.institution_id,
            "institution_name": inst.name if inst else None, "reason": r.reason, "stage": r.stage, "raised_by": r.raised_by,
            "raised_on": r.raised_on.isoformat(timespec="seconds"), "scrutiny_by": r.scrutiny_by, "approved_by": r.approved_by, "case_id": r.case_id,
            "dsc_serial": r.dsc_serial, "remarks": r.remarks, "updated_on": r.updated_on.isoformat(timespec="seconds"), "amount_paise": amount}


def bank_message(b: m.BankMessage) -> dict:
    return {"id": b.id, "received_at": b.received_at, "channel": b.channel, "kind": b.kind, "bank": b.bank, "bank_name": BANKS.get(b.bank, b.bank),
            "key_id": b.key_id, "signed_at": b.signed_at, "payload": mask_pii(open_pii(b.payload)), "evidence_id": b.evidence_id, "status": b.status,
            "reason": b.reason, "simulated": b.simulated, "scenario_id": b.scenario_id, "ref": b.ref}
