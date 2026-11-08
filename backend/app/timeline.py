"""Per-instrument history: issued, submitted, confirmed by the bank, verified, renewed / renumbered, matured, released,
closed. Each date carries the rule editions in force and how the relevant rule resolves on that date (kernel resolver).
Also flags gaps: a renewal was expected but no notice from the bank has arrived."""
from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .bank.simulator import BANKS

RULE_FOR = {"issued": "deposit.term_years", "renewed": "fdr.auto_renewal", "renumbered": "fdr.auto_renewal",
            "matured": "fdr.manual_renewal_after_maturity", "released": "release.fdr_instrument"}


def _rules(k, on: str, kind: str) -> dict:
    eds = [p["edition_id"] for p in k.rules.in_force(on)]
    key = RULE_FOR.get(kind)
    out = {"editions_in_force": eds, "rule": None}
    if key:
        r = k.rules.resolve(key, on)
        out["rule"] = {"key": key, "status": r.status, "value": r.value, "cites": r.cites}
    return out


def fdr_timeline(db: Session, k, f: m.Fdr, today: date | None = None) -> dict:
    today = today or date.today()
    ev: list[dict] = []

    def add(on: str, kind: str, label: str, source: str, **extra):
        ev.append({"date": on[:10], "at": on, "kind": kind, "label": label, "source": source, **_rules(k, on[:10], kind), **extra})

    add(f.issue_date.isoformat(), "issued", f"Issued by {BANKS.get(f.bank, f.bank)} as {f.instrument_no}", "institution declaration")
    add(f.submitted_on.isoformat(timespec="seconds"), "submitted", f"Submitted to AICTE as {f.id}", "portal")
    if f.renewal_of:
        add(f.submitted_on.isoformat(timespec="seconds"), "renewed", f"Submitted as the renewal of {f.renewal_of}", "portal", related=f.renewal_of)
    for b in db.scalars(select(m.BankMessage).where(m.BankMessage.ref == f.id).order_by(m.BankMessage.received_at)):
        if b.kind == "instrument_confirmation":
            add(b.received_at, "bank_confirmation", f"Bank confirmation {b.status.lower()}" + (f": {b.reason}" if b.reason else ""), "bank (SIMULATED)",
                evidence_id=b.evidence_id, simulated=b.simulated)
        elif b.kind == "lien_discharge":
            add(b.received_at, "released", "Bank confirmed the lien was discharged", "bank (SIMULATED)", evidence_id=b.evidence_id, simulated=b.simulated)
    for e in db.scalars(select(m.PortalEvent).where(m.PortalEvent.data.like(f'%"{f.id}"%')).order_by(m.PortalEvent.seq)):
        if e.type == "fdr_verified":
            add(e.at, "verified", "Verified by AICTE scrutiny", "portal audit", actor=e.actor)
        elif e.type == "fdr_discrepancy_flagged":
            add(e.at, "discrepancy", "Discrepancy flagged: " + json.loads(e.data).get("reason", ""), "portal audit", actor=e.actor)
    ins = k.instruments.get(f.instrument_id) or {}
    if ins.get("status") in ("RENEWED", "RENUMBERED"):
        ren = ins.get("renewal") or {}
        kind = "renewed" if ins["status"] == "RENEWED" else "renumbered"
        on = ren.get("renewed_on") or f.maturity_date.isoformat()
        add(on, kind, f"Bank {'auto-renewed' if kind == 'renewed' else 'renumbered'} the instrument; now {ins.get('superseded_by') or 'a new number'}",
            "bank (SIMULATED)", related=ins.get("superseded_by"))
    if f.renewed_by:
        add(f.maturity_date.isoformat(), "renewed", f"Replaced by renewal {f.renewed_by}", "portal", related=f.renewed_by)
    if f.maturity_date <= today:
        add(f.maturity_date.isoformat(), "matured", "Matured", "maturity date")
    else:
        add(f.maturity_date.isoformat(), "matures", f"Matures in {(f.maturity_date - today).days} days", "maturity date", future=True)
    for r in db.scalars(select(m.ReleaseRequest).where(m.ReleaseRequest.fdr_id == f.id)):
        if r.stage == "COMPLETED":
            add(r.updated_on.isoformat(timespec="seconds"), "released", f"Release {r.id} completed", "portal")
    if f.status == "closed":
        add(f.submitted_on.isoformat(timespec="seconds"), "closed", f.closed_reason or "Closed", "portal")
    ev.sort(key=lambda e: (e["date"], e["at"]))
    return {"fdr_id": f.id, "events": ev, "gaps": gaps(db, k, f, today)}


def gaps(db: Session, k, f: m.Fdr, today: date | None = None) -> list[dict]:
    """A renewal is expected once a live FDR has matured. If neither a renewal FDR nor a bank renewal / renumbering notice
    exists, that is a gap. A submitted renewal that its bank has not confirmed within 7 days is also a gap."""
    today = today or date.today()
    out = []
    ins = k.instruments.get(f.instrument_id) or {}
    bank_renewed = ins.get("status") in ("RENEWED", "RENUMBERED")
    if f.status in ("verified", "pending", "discrepancy") and f.maturity_date < today and not f.renewed_by and not bank_renewed:
        out.append({"kind": "renewal_notice_missing", "since": f.maturity_date.isoformat(), "days": (today - f.maturity_date).days,
                    "label": f"Matured {(today - f.maturity_date).days} days ago; no renewal FDR and no renewal notice from {BANKS.get(f.bank, f.bank)}"})
    if f.renewal_of and not any(k.evidence_valid(c["evidence_id"]) for c in ins.get("confirmations", [])):
        waited = (today - f.submitted_on.date()).days
        if waited > 7:
            out.append({"kind": "renewal_unconfirmed", "since": f.submitted_on.date().isoformat(), "days": waited,
                        "label": f"Renewal submitted {waited} days ago; the issuing bank has not confirmed it"})
    return out
