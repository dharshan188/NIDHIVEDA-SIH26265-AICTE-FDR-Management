"""Dashboards, FDRs, institutions, notifications, messages. Every number is computed from the database."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from .. import documents, portal_audit, timeline
from .. import models as m
from .. import serialize as S
from ..db import get_db
from ..deps import Principal, current, institution_scope, require
from ..domain import fdr as fdr_svc
from ..nudge import notify
from ..nudge.outbox import title
from ..nudge.recipients import audiences
from ..nudge.worker import acknowledge
from ..ledger import LEDGER

router = APIRouter(tags=["data"])


def _bucket_sql(today: date):
    soon = today + timedelta(days=90)
    return case((and_(m.Fdr.status == "verified", m.Fdr.maturity_date <= soon), "maturing"),
                (m.Fdr.status == "verified", "active"), else_=m.Fdr.status)


def _stats(db: Session, inst_id: str | None = None) -> dict:
    today = date.today()
    b = _bucket_sql(today).label("b")
    q = select(b, func.count(), func.coalesce(func.sum(m.Fdr.amount_paise), 0)).group_by(b)
    if inst_id:
        q = q.where(m.Fdr.institution_id == inst_id)
    by = {k: {"count": 0, "amount_paise": 0} for k in ("active", "maturing", "pending", "discrepancy", "released", "closed")}
    for k, c, a in db.execute(q):
        by[k] = {"count": c, "amount_paise": int(a)}
    total = {"count": sum(v["count"] for v in by.values()), "amount_paise": sum(v["amount_paise"] for v in by.values())}
    rel = select(func.count(), func.coalesce(func.sum(m.Fdr.amount_paise), 0)).select_from(m.ReleaseRequest).join(
        m.Fdr, m.Fdr.id == m.ReleaseRequest.fdr_id, isouter=True).where(m.ReleaseRequest.stage.in_(("SUBMITTED", "SCRUTINY_DONE", "APPROVED")))
    if inst_id:
        rel = rel.where(m.ReleaseRequest.institution_id == inst_id)
    rc, ra = db.execute(rel).one()
    disc_inst = db.scalar(select(func.count(func.distinct(m.Fdr.institution_id))).where(m.Fdr.status == "discrepancy"))
    week = datetime.now() - timedelta(days=7)
    new_inst = db.scalar(select(func.count(func.distinct(m.Fdr.institution_id))).where(m.Fdr.submitted_on >= week))
    return {"as_of": today.isoformat(), "by_bucket": by, "total": total, "open_release_requests": {"count": rc, "amount_paise": int(ra)},
            "fdrs_with_discrepancy": by["discrepancy"]["count"], "institutions_with_discrepancy": disc_inst,
            "institutions": db.scalar(select(func.count()).select_from(m.Institution)), "institutions_submitting_this_week": new_inst}


def _compliance(db: Session) -> dict:
    """Per-institution compliance from its FDRs (worst state wins)."""
    rank = case((m.Fdr.status == "discrepancy", 3), (m.Fdr.status == "pending", 2), (m.Fdr.status == "verified", 1), else_=0)
    sub = select(m.Institution.id, func.coalesce(func.max(rank), 0).label("r")).join(m.Fdr, m.Fdr.institution_id == m.Institution.id, isouter=True) \
        .group_by(m.Institution.id).subquery()
    out = {"compliant": 0, "pending": 0, "discrepancy": 0, "no_valid_fdr": 0}
    names = {3: "discrepancy", 2: "pending", 1: "compliant", 0: "no_valid_fdr"}
    for r, c in db.execute(select(sub.c.r, func.count()).group_by(sub.c.r)):
        out[names[r]] = c
    return out


def _maturing(db: Session, inst_id: str | None = None, limit: int = 5) -> list[dict]:
    today = date.today()
    q = select(m.Fdr, m.Institution).join(m.Institution).where(m.Fdr.status == "verified", m.Fdr.maturity_date <= today + timedelta(days=90),
                                                                m.Fdr.renewed_by.is_(None)).order_by(m.Fdr.maturity_date).limit(limit)
    if inst_id:
        q = q.where(m.Fdr.institution_id == inst_id)
    return [S.fdr(f, i, today) for f, i in db.execute(q)]


def _recent(db: Session, limit: int = 5, inst_id: str | None = None, status: str | None = None) -> list[dict]:
    q = select(m.Fdr, m.Institution).join(m.Institution).order_by(m.Fdr.submitted_on.desc()).limit(limit)
    if inst_id:
        q = q.where(m.Fdr.institution_id == inst_id)
    if status:
        q = q.where(m.Fdr.status == status)
    return [S.fdr(f, i) for f, i in db.execute(q)]


@router.get("/dashboard/aicte")
def dash_aicte(p: Principal = Depends(require("AICTE_OFFICIAL")), db: Session = Depends(get_db)):
    k = LEDGER.kernel()
    return {"stats": _stats(db), "recent": _recent(db, 5), "maturing": _maturing(db), "compliance": _compliance(db),
            "last_bank_sync": db.scalar(select(func.max(m.BankMessage.received_at))),
            "pipeline": {"bank_unconfirmed_pending": sum(1 for f in db.scalars(select(m.Fdr).where(m.Fdr.status == "pending"))
                                                         if not any(k.evidence_valid(c["evidence_id"]) for c in k.instruments.get(f.instrument_id, {}).get("confirmations", []))),
                         "renewals": db.scalar(select(func.count()).select_from(m.Fdr).where(m.Fdr.renewal_of.is_not(None))),
                         "release_by_stage": dict(db.execute(select(m.ReleaseRequest.stage, func.count()).group_by(m.ReleaseRequest.stage)).all())}}


@router.get("/dashboard/auditor")
def dash_auditor(p: Principal = Depends(require("AUDITOR")), db: Session = Depends(get_db)):
    return {"stats": _stats(db), "recent": _recent(db, 5), "maturing": _maturing(db), "compliance": _compliance(db),
            "last_bank_sync": db.scalar(select(func.max(m.BankMessage.received_at)))}


@router.get("/dashboard/institution/{inst_id}")
def dash_inst(inst_id: str, p: Principal = Depends(current), db: Session = Depends(get_db)):
    institution_scope(p, inst_id)
    inst = db.get(m.Institution, inst_id)
    if not inst:
        raise HTTPException(404, "not found")
    fdrs = [S.fdr(f, inst) for f in db.scalars(select(m.Fdr).where(m.Fdr.institution_id == inst_id).order_by(m.Fdr.submitted_on))]
    acts = db.scalars(select(m.PortalEvent).where(m.PortalEvent.actor == f"institution:{inst_id}").order_by(m.PortalEvent.seq.desc()).limit(5)).all()
    return {"institution": S.institution(inst), "stats": _stats(db, inst_id), "fdrs": fdrs, "maturing": _maturing(db, inst_id, 50),
            "activity": [{"at": a.at, "type": a.type, "data": a.data} for a in acts],
            "last_bank_sync": db.scalar(select(func.max(m.BankMessage.received_at)).join(m.Fdr, m.Fdr.id == m.BankMessage.ref).where(m.Fdr.institution_id == inst_id))}


@router.get("/meta/freshness")
def freshness(p: Principal = Depends(current), db: Session = Depends(get_db)):
    """For the "Data as of" bar on every page: when these figures were read (server clock, IST) and the newest bank message
    behind them (scoped to the institution for institution users). Every figure is a live query, so "as of" is now."""
    from ..nudge.clock import iso, now_ist
    q = select(func.max(m.BankMessage.received_at))
    if p.user.role == "INSTITUTION":
        q = q.join(m.Fdr, m.Fdr.id == m.BankMessage.ref).where(m.Fdr.institution_id == p.user.institution_id)
    return {"data_as_of": iso(now_ist()), "timezone": "Asia/Kolkata", "last_bank_message_at": db.scalar(q), "bank_simulated": True,
            "source": "live database queries"}


# ------------------------------------------------------------------ FDRs
@router.get("/fdrs")
def list_fdrs(p: Principal = Depends(current), db: Session = Depends(get_db), q: str = "", bucket: str = "", bank: str = "", state: str = "",
              institution_id: str = "", bank_confirmed: str = "", sort: str = "submitted", page: int = Query(1, ge=1), size: int = Query(12, ge=1, le=200)):
    today = date.today()
    stmt = select(m.Fdr, m.Institution).join(m.Institution)
    if p.user.role == "INSTITUTION":
        stmt = stmt.where(m.Fdr.institution_id == p.user.institution_id)
    elif institution_id:
        stmt = stmt.where(m.Fdr.institution_id == institution_id)
    if bucket:
        stmt = stmt.where(_bucket_sql(today) == bucket)
    if bank:
        stmt = stmt.where(m.Fdr.bank == bank)
    if state:
        stmt = stmt.where(m.Institution.state == state)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(m.Fdr.id).like(like), func.lower(m.Institution.name).like(like), func.lower(m.Fdr.instrument_no).like(like)))
    rows = db.execute(stmt).all()
    k = LEDGER.kernel()

    def confirmed(f):
        ins = k.instruments.get(f.instrument_id)
        return bool(ins and any(k.evidence_valid(c["evidence_id"]) for c in ins["confirmations"]))
    items = []
    for f, i in rows:
        d = S.fdr(f, i, today)
        d["bank_confirmed"] = confirmed(f)
        items.append(d)
    if bank_confirmed in ("0", "1"):
        items = [d for d in items if d["bank_confirmed"] == (bank_confirmed == "1")]
    key = {"submitted": lambda d: d["submitted_on"], "maturity": lambda d: d["maturity_date"], "amount": lambda d: d["amount_paise"]}.get(sort, lambda d: d["submitted_on"])
    items.sort(key=key, reverse=sort in ("submitted", "amount"))
    counts: dict[str, int] = {}
    for d in items:
        counts[d["bucket"]] = counts.get(d["bucket"], 0) + 1
    return {"total": len(items), "amount_paise": sum(d["amount_paise"] for d in items), "counts": counts, "page": page, "size": size,
            "items": items[(page - 1) * size: page * size]}


def _get_fdr(db: Session, p: Principal, fid: str) -> m.Fdr:
    f = db.get(m.Fdr, fid)
    if not f:
        raise HTTPException(404, "not found")
    institution_scope(p, f.institution_id)
    return f


@router.get("/fdrs/{fid}")
def get_fdr(fid: str, p: Principal = Depends(current), db: Session = Depends(get_db)):
    f = _get_fdr(db, p, fid)
    k = LEDGER.kernel()
    inst = db.get(m.Institution, f.institution_id)
    docs = db.scalars(select(m.FdrDocument).where(m.FdrDocument.fdr_id == fid)).all()
    rel = db.scalars(select(m.ReleaseRequest).where(m.ReleaseRequest.obligation_id == f.obligation_id).order_by(m.ReleaseRequest.raised_on.desc())).first()
    hist = [{"at": e.at, "actor": e.actor, "type": e.type, "data": e.data} for e in
            db.scalars(select(m.PortalEvent).where(m.PortalEvent.data.like(f'%"{fid}"%')).order_by(m.PortalEvent.seq))]
    kev = [{"at": e.at, "actor": e.actor, "type": e.type, "seq": e.seq} for e in
           db.scalars(select(m.KernelEvent).where(or_(m.KernelEvent.data.like(f'%"{f.obligation_id}"%'), m.KernelEvent.data.like(f'%"{f.instrument_no}"%')))
                      .order_by(m.KernelEvent.seq))]
    noc = next((n for n in k.nocs.values() if n["obligation_id"] == f.obligation_id), None)
    return {"fdr": S.fdr(f, inst), "institution": S.institution(inst), "comparison": fdr_svc.comparison(k, f),
            "documents": [documents.describe(d) for d in docs],
            "release": S.release(rel) if rel else None, "noc": noc, "portal_history": hist, "ledger_events": kev,
            "renewal": [v for (iid, _), v in k.renewal_requests.items() if iid == f.instrument_id]}


@router.post("/fdrs")
async def upload_fdr(p: Principal = Depends(require("INSTITUTION")), db: Session = Depends(get_db),
                     bank: str = Form(), branch: str = Form(), instrument_no: str = Form(), amount_rupees: int = Form(), rate_bp: int = Form(710),
                     issue_date: date = Form(), maturity_date: date = Form(), renewal_of: str | None = Form(None),
                     files: list[UploadFile] = File(...), doc_types: list[str] | None = Form(None)):
    """Step 3 of the upload wizard: one multipart request with the details and the documents (PDF only).
    `doc_types` lines up with `files`; without it the first file is the scanned FDR and the second the lien letter."""
    if amount_rupees < 20_00_000:
        raise HTTPException(422, "minimum prescribed amount is ₹20,00,000")
    if (maturity_date - issue_date).days < 3 * 365 - 5:
        raise HTTPException(422, "tenure must be at least 3 years")
    if issue_date > date.today():
        raise HTTPException(422, "issue date cannot be in the future")
    if len(files) < 2:
        raise HTTPException(422, "upload the scanned FDR and the bank lien letter")
    if renewal_of:
        _get_fdr(db, p, renewal_of)
    kinds = doc_types or (["fdr_scan", "lien_letter"] + ["other"] * (len(files) - 2))
    if len(kinds) != len(files):
        raise HTTPException(422, "doc_types must list one type per file")
    if not {"fdr_scan", "lien_letter"} <= set(kinds):
        raise HTTPException(422, "include the scanned FDR and the bank lien letter")
    docs = []
    for uf, kind in zip(files, kinds):
        data = await uf.read(documents.MAX_BYTES + 1)
        docs.append(documents.ingest(db, name=uf.filename or "document.pdf", content_type=uf.content_type, data=data, doc_type=kind, actor=p.actor))
    f = fdr_svc.submit(db, inst_id=p.user.institution_id, actor=p.actor, bank=bank, branch=branch, instrument_no=instrument_no.strip(),
                       amount_paise=amount_rupees * 100, rate_bp=rate_bp, issue=issue_date, maturity=maturity_date, docs=docs, renewal_of=renewal_of)
    stored = db.scalars(select(m.FdrDocument).where(m.FdrDocument.fdr_id == f.id)).all()
    return {"fdr": S.fdr(f, db.get(m.Institution, f.institution_id)), "documents": [documents.describe(d) for d in stored]}


@router.post("/fdrs/{fid}/documents")
async def add_document(fid: str, p: Principal = Depends(require("INSTITUTION")), db: Session = Depends(get_db),
                       file: UploadFile = File(...), doc_type: str = Form()):
    """Adds a missing or replacement document to an existing FDR (the missing-documents report links here)."""
    f = _get_fdr(db, p, fid)
    data = await file.read(documents.MAX_BYTES + 1)
    meta = documents.ingest(db, name=file.filename or "document.pdf", content_type=file.content_type, data=data, doc_type=doc_type, actor=p.actor)
    row = documents.add_row(db, f.id, meta, datetime.now())
    db.flush()
    portal_audit.record(db, "document_added", p.actor, {"fdr_id": f.id, "document_id": row.id, "doc_type": doc_type, "sha256": meta["sha256"]})
    db.commit()
    return {"document": documents.describe(row)}


@router.post("/fdrs/{fid}/bank-confirmation")
def bank_confirm(fid: str, p: Principal = Depends(require("AICTE_OFFICIAL")), db: Session = Depends(get_db)):
    f = _get_fdr(db, p, fid)
    msg = fdr_svc.request_bank_confirmation(db, f)
    return {"message": msg, "fdr": S.fdr(db.get(m.Fdr, fid)), "comparison": fdr_svc.comparison(LEDGER.kernel(), db.get(m.Fdr, fid))}


class VerifyIn(BaseModel):
    note: str | None = Field(None, max_length=1000)


@router.post("/fdrs/{fid}/verify")
def verify_fdr(fid: str, body: VerifyIn, p: Principal = Depends(require("AICTE_OFFICIAL")), db: Session = Depends(get_db)):
    f = fdr_svc.verify(db, _get_fdr(db, p, fid), p.actor, body.note)
    return {"fdr": S.fdr(f)}


class FlagIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


@router.post("/fdrs/{fid}/discrepancy")
def flag_fdr(fid: str, body: FlagIn, p: Principal = Depends(require("AICTE_OFFICIAL")), db: Session = Depends(get_db)):
    return {"fdr": S.fdr(fdr_svc.flag(db, _get_fdr(db, p, fid), p.actor, body.reason))}


class RenewalIn(BaseModel):
    new_number: str
    new_maturity: date


@router.post("/fdrs/{fid}/renewal-check")
def renewal_check(fid: str, body: RenewalIn, p: Principal = Depends(current), db: Session = Depends(get_db)):
    """Rule check for a manual renewal on today's date. Unverified, unspecified or conflicting rules escalate."""
    f = _get_fdr(db, p, fid)
    return {"outcome": fdr_svc.renewal_decision(db, f, p.actor, body.new_number, body.new_maturity)}


@router.get("/fdrs/{fid}/documents/{doc_id}")
def get_document(fid: str, doc_id: int, p: Principal = Depends(current), db: Session = Depends(get_db)):
    from fastapi.responses import Response
    _get_fdr(db, p, fid)
    d = db.get(m.FdrDocument, doc_id)
    if not d or d.fdr_id != fid:
        raise HTTPException(404, "not found")
    data = documents.read(db, d, p.actor, p.user.role)
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{d.name}"', "X-Content-Type-Options": "nosniff",
                             "X-Document-SHA256": d.sha256})


@router.post("/fdrs/{fid}/documents/{doc_id}/verify")
def verify_document(fid: str, doc_id: int, p: Principal = Depends(current), db: Session = Depends(get_db)):
    """Re-checks a stored document: fetch the ciphertext, decrypt, SHA-256 must equal the value recorded at upload."""
    _get_fdr(db, p, fid)
    d = db.get(m.FdrDocument, doc_id)
    if not d or d.fdr_id != fid:
        raise HTTPException(404, "not found")
    return {**documents.verify_integrity(db, d, p.actor, p.user.role), "document": documents.describe(d)}


@router.post("/documents/precheck")
async def precheck_document(p: Principal = Depends(require("INSTITUTION")), db: Session = Depends(get_db), file: UploadFile = File(...)):
    """Upload page, per file: the same content checks and malware scan as a submission, before anything is stored."""
    data = await file.read(documents.MAX_BYTES + 1)
    return documents.precheck(db, name=file.filename or "document.pdf", content_type=file.content_type, data=data, actor=p.actor)


@router.get("/fdrs/{fid}/timeline")
def fdr_timeline(fid: str, p: Principal = Depends(current), db: Session = Depends(get_db)):
    """Issued, renewed, renumbered, matured, released ... with the rule editions in force on each date, and any renewal gap."""
    f = _get_fdr(db, p, fid)
    out = timeline.fdr_timeline(db, LEDGER.kernel(), f)
    out["reminders"] = [{"id": n.id, "at": n.at, "window": n.window, "rung": n.rung, "ack_at": n.ack_at, "key": n.key}
                        for n in db.scalars(select(m.Notification).where(m.Notification.ref == fid, m.Notification.key.is_not(None))
                                            .order_by(m.Notification.at))]
    return out


@router.get("/renewals/gaps")
def renewal_gaps(p: Principal = Depends(current), db: Session = Depends(get_db)):
    """Every live FDR where a renewal is expected but neither a renewal FDR nor a bank notice has arrived."""
    k, today = LEDGER.kernel(), date.today()
    q = select(m.Fdr, m.Institution).join(m.Institution).where(m.Fdr.status.in_(("verified", "pending", "discrepancy")))
    if p.user.role == "INSTITUTION":
        q = q.where(m.Fdr.institution_id == p.user.institution_id)
    rows = []
    for f, i in db.execute(q.order_by(m.Fdr.maturity_date)):
        for g in timeline.gaps(db, k, f, today):
            rows.append({**g, "fdr_id": f.id, "institution_id": i.id, "institution": i.name, "bank": f.bank, "maturity_date": f.maturity_date.isoformat(),
                         "amount_paise": f.amount_paise})
    return {"as_of": today.isoformat(), "total": len(rows), "items": rows}


# ------------------------------------------------------------------ institutions
@router.get("/institutions")
def list_institutions(p: Principal = Depends(require("AICTE_OFFICIAL", "AUDITOR")), db: Session = Depends(get_db), q: str = "", state: str = "",
                      compliance: str = "", page: int = 1, size: int = 14):
    rank = case((m.Fdr.status == "discrepancy", 3), (m.Fdr.status == "pending", 2), (m.Fdr.status == "verified", 1), else_=0)
    live = case((m.Fdr.status.in_(("verified", "pending", "discrepancy")), 1), else_=0)
    amt = case((m.Fdr.status.in_(("verified", "pending", "discrepancy")), m.Fdr.amount_paise), else_=0)
    stmt = select(m.Institution, func.coalesce(func.max(rank), 0), func.coalesce(func.sum(live), 0), func.coalesce(func.sum(amt), 0)) \
        .join(m.Fdr, m.Fdr.institution_id == m.Institution.id, isouter=True).group_by(m.Institution.id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(m.Institution.name).like(like), m.Institution.aicte_id.like(like), func.lower(m.Institution.city).like(like)))
    if state:
        stmt = stmt.where(m.Institution.state == state)
    names = {3: "Discrepancy", 2: "Pending Verification", 1: "Compliant", 0: "No Valid FDR"}
    rows = [{**S.institution(i), "compliance": names[r], "live_fdrs": int(n), "amount_paise": int(a)} for i, r, n, a in db.execute(stmt.order_by(m.Institution.id))]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["compliance"]] = counts.get(r["compliance"], 0) + 1
    if compliance:
        rows = [r for r in rows if r["compliance"] == compliance]
    return {"total": len(rows), "counts": counts, "states": sorted({s for (s,) in db.execute(select(m.Institution.state).distinct())}),
            "items": rows[(page - 1) * size: page * size]}


@router.get("/institutions/{inst_id}")
def get_institution(inst_id: str, p: Principal = Depends(current), db: Session = Depends(get_db)):
    institution_scope(p, inst_id)
    i = db.get(m.Institution, inst_id)
    if not i:
        raise HTTPException(404, "not found")
    fdrs = [S.fdr(f, i) for f in db.scalars(select(m.Fdr).where(m.Fdr.institution_id == inst_id).order_by(m.Fdr.submitted_on.desc()))]
    return {"institution": S.institution(i), "fdrs": fdrs, "stats": _stats(db, inst_id)}


# ------------------------------------------------------------------ notifications and messages
def _audiences(p: Principal) -> list[str]:
    return audiences(p.user)


@router.get("/notifications")
def notifications(p: Principal = Depends(current), db: Session = Depends(get_db), limit: int = 30):
    aud = _audiences(p)
    rows = db.scalars(select(m.Notification).where(m.Notification.audience.in_(aud)).order_by(m.Notification.at.desc()).limit(limit)).all()
    unread = db.scalar(select(func.count()).select_from(m.Notification).where(m.Notification.audience.in_(aud), m.Notification.read.is_(False)))
    hi = p.user.lang == "hi"
    return {"unread": unread, "items": [{"id": n.id, "at": n.at, "kind": n.kind, "text": (n.text_hi if hi and n.text_hi else n.text), "ref": n.ref,
                                         "read": n.read, "audience": n.audience, "rung": n.rung, "title": title(n, p.user.lang or "en"),
                                         "ack_at": n.ack_at} for n in rows]}


@router.post("/notifications/read")
def mark_read(p: Principal = Depends(current), db: Session = Depends(get_db), id: int | None = None):
    q = select(m.Notification).where(m.Notification.audience.in_(_audiences(p)))
    if id:   # opening one notice acknowledges it (Nudge Ladder); "mark all as read" does not
        n = db.scalars(q.where(m.Notification.id == id)).first()
        if not n:
            raise HTTPException(404, "not found")
        acknowledge(db, n, p.user, "open")
        return {"ok": True, "acknowledged": True}
    for n in db.scalars(q):
        n.read = True
    db.commit()
    return {"ok": True}


class MsgIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.get("/messages/{inst_id}")
def messages(inst_id: str, p: Principal = Depends(current), db: Session = Depends(get_db)):
    institution_scope(p, inst_id)
    if p.user.role == "AUDITOR":
        raise HTTPException(403, "your role cannot do this")
    rows = db.scalars(select(m.Message).where(m.Message.institution_id == inst_id).order_by(m.Message.at)).all()
    return {"items": [{"id": r.id, "sender": r.sender, "author": r.author, "at": r.at.isoformat(timespec="seconds"), "text": r.text} for r in rows]}


@router.post("/messages/{inst_id}")
def send_message(inst_id: str, body: MsgIn, p: Principal = Depends(require("INSTITUTION", "AICTE_OFFICIAL")), db: Session = Depends(get_db)):
    institution_scope(p, inst_id)
    db.add(m.Message(institution_id=inst_id, sender="institution" if p.user.role == "INSTITUTION" else "aicte", author=p.user.username,
                     at=datetime.now(), text=body.text))
    inst = db.get(m.Institution, inst_id)
    sender = {"en": inst.name, "hi": inst.name} if p.user.role == "INSTITUTION" and inst else {"en": "AICTE", "hi": "AICTE"}
    notify(db, "aicte" if p.user.role == "INSTITUTION" else f"institution:{inst_id}", "message", {"sender": sender, "text": body.text[:140]},
           ref=inst_id, institution_id=inst_id)
    db.commit()
    return {"ok": True}


@router.get("/obligations")
def obligations(p: Principal = Depends(current), db: Session = Depends(get_db), instrument_class: str = "ONLINE"):
    """Online (RTGS) deposits with their funding confidence, scoped to the caller's institution."""
    k = LEDGER.kernel()
    q = select(m.Obligation, m.Institution).join(m.Institution).where(m.Obligation.instrument_class == instrument_class)
    if p.user.role == "INSTITUTION":
        q = q.where(m.Obligation.institution_id == p.user.institution_id)
    out = []
    for o, i in db.execute(q.order_by(m.Obligation.obligation_id)):
        fb = k.funding_breakdown(o.obligation_id) if o.obligation_id in k.obligations else {}
        out.append({"obligation_id": o.obligation_id, "institution_id": i.id, "institution_name": i.name, "programme": o.programme,
                    "required_paise": o.amount_paise, "funding": {c: v for c, v in fb.items() if v},
                    "liability": k.liability_register(o.obligation_id) if o.obligation_id in k.obligations else None,
                    "refunds": [rid for rid, r in k.refunds.items() if r["obligation_id"] == o.obligation_id]})
    return {"items": out}
