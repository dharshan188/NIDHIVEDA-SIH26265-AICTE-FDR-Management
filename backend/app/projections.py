"""Mirror kernel state into SQL tables, in the same transaction as the events.

Only rows touched by the new events are written. The database triggers and constraints then check
the money invariants independently of the kernel.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m


def project(db: Session, k, events: list) -> None:
    touched_credits: set[str] = set()
    touched_refunds: set[str] = set()
    touched_obligations: set[str] = set()
    for ev in events:
        d = ev.data
        t = ev.type
        if t == "institution_registered" and db.get(m.Institution, d["inst_id"]) is None:
            db.add(m.Institution(id=d["inst_id"], aicte_id=f"LEGACY-{d['inst_id']}", name=d["name"], type="Unknown (legacy import)",
                                 state="Unknown", city="Unknown", email="", phone="", principal="", established=0, intake=0))
            db.flush()
        elif t == "obligation_created":
            db.add(m.Obligation(obligation_id=d["obligation_id"], institution_id=d["inst_id"], programme=d["programme"],
                                instrument_class=d["instrument_class"], amount_paise=d["amount"], reference=d.get("reference"), legacy=d.get("legacy", False)))
            db.flush()
        elif t == "instrument_registered":
            db.add(m.Instrument(instrument_id=d["instrument_id"], obligation_id=d["obligation_id"], number=d["number"], bank=d["bank"],
                                amount_paise=d["amount"], issue_date=d["issue_date"], maturity_date=d["maturity_date"], status="ACTIVE", source=d["source"]))
            db.flush()
            touched_obligations.add(d["obligation_id"])
        elif t == "evidence_recorded":
            env = d["envelope"]
            p, kind = env["payload"], env["kind"]
            if kind == "credit_advice":
                cid = "CR-" + p["utr"]
                db.add(m.BankCredit(credit_id=cid, utr=p["utr"], amount_paise=p["amount"], kind="deposit", bank=env["bank"],
                                    evidence_id=d["evidence_id"], value_date=p["value_date"]))
                db.flush()
            elif kind == "return_advice":
                db.add(m.BankCredit(credit_id="RET-" + p["return_utr"], utr=p["return_utr"], amount_paise=p["amount"], kind="return",
                                    bank=env["bank"], evidence_id=d["evidence_id"], value_date=ev.at[:10]))
                db.flush()
                touched_refunds.add(k.attempt_by_utr[p["original_utr"]][0])
            elif kind in ("debit_advice",):
                touched_refunds.add(p["refund_id"])
            elif kind == "credit_confirmation":
                touched_refunds.add(k.attempt_by_utr[p["utr"]][0])
            elif kind in ("instrument_confirmation", "lien_discharge"):
                no = p["instrument_no"]
                iid = k.instr_by_no.get(no)
                if iid:
                    touched_obligations.add(k.instruments[iid]["obligation_id"])
        elif t in ("allocated", "competing_claim"):
            touched_credits.add(d["credit_id"])
        elif t == "allocation_reversed":
            touched_credits.add(k.allocations[d["alloc_id"]]["credit_id"])
        elif t == "dispute_resolved":
            touched_credits.add(k.disputes[d["dispute_id"]]["credit_id"])
        elif t in ("refund_authorised", "payment_initiated"):
            touched_refunds.add(d["refund_id"])
        elif t in ("noc_issued",):
            touched_obligations.add(d["obligation_id"])
        elif t in ("signer_compromised", "signer_ended"):
            # confirmations signed with this key may no longer count: re-evaluate every FDR that relied on one
            for ins in k.instruments.values():
                if any(k.evidence[c["evidence_id"]]["key_id"] == d["key_id"] for c in ins["confirmations"]):
                    touched_obligations.add(ins["obligation_id"])
    for cid in touched_credits:
        _sync_allocations(db, k, cid)
    for rid in touched_refunds:
        _sync_refund(db, k, rid)
    for oid in touched_obligations:
        _sync_instruments(db, k, oid)
        fdr = db.scalars(select(m.Fdr).where(m.Fdr.obligation_id == oid)).first()
        if fdr:
            refresh_fdr(db, k, fdr)


def _sync_allocations(db: Session, k, credit_id: str) -> None:
    want = {a["alloc_id"]: a for a in k._allocs_on_credit(credit_id)}
    have = {r.alloc_id: r for r in db.scalars(select(m.Allocation).where(m.Allocation.credit_id == credit_id))}
    # shrink/deactivate first, then grow/insert, so the sum triggers never see a transient over-allocation
    shrink = [a for aid, a in want.items() if aid in have and (not a["active"] or a["amount"] <= have[aid].amount_paise)]
    grow = [a for aid, a in want.items() if a not in shrink]
    for a in shrink + grow:
        row = have.get(a["alloc_id"])
        if row is None:
            db.add(m.Allocation(alloc_id=a["alloc_id"], credit_id=a["credit_id"], obligation_id=a["obligation_id"],
                                amount_paise=a["amount"], basis=a["basis"], active=a["active"]))
        else:
            row.amount_paise, row.basis, row.active = a["amount"], a["basis"], a["active"]
        db.flush()


def _sync_refund(db: Session, k, rid: str) -> None:
    r = k.refunds[rid]
    row = db.get(m.Refund, rid)
    if row is None:
        row = m.Refund(refund_id=rid, obligation_id=r["obligation_id"], institution_id=r["inst_id"], amount_paise=r["amount"], rail=r["rail"],
                       state=r["state"], approver=r["approver"], authorised_at=r["history"][0][0])
        db.add(row)
    row.state = r["state"]
    db.flush()
    have = {a.attempt_no: a for a in db.scalars(select(m.PaymentAttempt).where(m.PaymentAttempt.refund_id == rid))}
    for i, att in enumerate(r["attempts"]):
        a = have.get(i)
        if a is None:
            a = m.PaymentAttempt(refund_id=rid, attempt_no=i, utr=att["utr"], amount_paise=att["amount"], status=att["status"], debited_at=att["debited_at"])
            db.add(a)
        a.status = att["status"]
        a.settled_at = att.get("settled_at")
        a.returned_at = att.get("returned_at")
        a.return_reason = att.get("return_reason")
        a.returned_after_settlement = bool(att.get("returned_after_settlement"))
        db.flush()


def _sync_instruments(db: Session, k, oid: str) -> None:
    for iid, ins in k.instruments.items():
        if ins["obligation_id"] != oid:
            continue
        row = db.get(m.Instrument, iid)
        if row is None:
            row = m.Instrument(instrument_id=iid, obligation_id=oid, number=ins["number"], bank=ins["bank"], amount_paise=ins["amount"],
                               issue_date=ins.get("issue_date"), maturity_date=ins["maturity_date"], status=ins["status"], source=ins["source"])
            db.add(row)
        row.status = ins["status"]
        row.superseded_by = ins["superseded_by"]
        db.flush()


# ------------------------------------------------------------------ FDR status
def bank_view(k, oid: str) -> dict:
    """What the latest *valid* bank confirmation says about the obligation's current instrument."""
    ins = k.current_instrument(oid)
    if not ins:
        return {"instrument": None, "confirmation": None}
    valid = [c for c in ins["confirmations"] if k.evidence_valid(c["evidence_id"])]
    invalid = [c for c in ins["confirmations"] if not k.evidence_valid(c["evidence_id"])]
    last = max(valid, key=lambda c: c["as_of"]) if valid else None
    return {"instrument": ins, "confirmation": last, "invalid_confirmations": invalid}


def inr(paise: int) -> str:
    """Indian digit grouping: 2500000 rupees -> 25,00,000."""
    s = str(paise // 100)
    head, tail = s[:-3], s[-3:]
    while len(head) > 2:
        tail = head[-2:] + "," + tail
        head = head[:-2]
    return "₹" + (head + "," + tail if head else tail)


def mismatches(ins: dict, conf: dict) -> list[str]:
    if conf["status"] == "NOT_FOUND":
        return ["issuing bank has no record of this instrument"]
    out = []
    if conf["amount"] != ins["amount"]:
        out.append(f"bank-confirmed principal {inr(conf['amount'])} differs from declared {inr(ins['amount'])}")
    if conf["maturity_date"][:10] != ins["maturity_date"][:10]:
        out.append(f"bank maturity {conf['maturity_date'][:10]} differs from declared {ins['maturity_date'][:10]}")
    if conf["status"] != "ACTIVE":
        out.append(f"bank reports status {conf['status']}")
    if conf["lien_holder"] != "AICTE":
        out.append(f"lien marked in favour of {conf['lien_holder']}, not AICTE")
    return out


def refresh_fdr(db: Session, k, fdr: m.Fdr) -> None:
    oid = fdr.obligation_id
    discharged = [n for n in k.nocs.values() if n["obligation_id"] == oid and n["state"] == "LIEN_DISCHARGED"]
    bv = bank_view(k, oid)
    ins, conf = bv["instrument"], bv["confirmation"]
    if ins and ins["number"] != fdr.instrument_no:   # bank reported auto-renewal / renumbering
        fdr.instrument_id, fdr.instrument_no = ins["instrument_id"], ins["number"]
        fdr.maturity_date = date.fromisoformat(ins["maturity_date"][:10])
    if discharged:
        fdr.status = "closed" if fdr.closed_reason else "released"
    elif conf is None:
        fdr.status = "discrepancy" if fdr.discrepancy_reason else "pending"
    else:
        bad = mismatches(ins, conf)
        if bad:
            fdr.status, fdr.discrepancy_reason = "discrepancy", "Bank: " + "; ".join(bad)
        elif fdr.discrepancy_reason and not fdr.discrepancy_reason.startswith("Bank:"):
            fdr.status = "discrepancy"   # officer-recorded document discrepancy stays until resolved
        else:
            if fdr.discrepancy_reason and fdr.discrepancy_reason.startswith("Bank:"):
                fdr.discrepancy_reason = None
            fdr.status = "verified" if fdr.scrutinised else "pending"
    db.flush()
