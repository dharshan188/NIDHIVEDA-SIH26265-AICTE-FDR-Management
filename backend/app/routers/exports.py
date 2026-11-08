"""Missing-documents / exception report, and PDF export (any table, the report, the FDR evidence packet).

Required documents per instrument class (REQUIRED). An item is listed when its document is
  absent      no document of that type on record (online deposits: no bank credit advice)
  expired     the instrument it evidences has matured without renewal or release
  unverified  on record but not trusted yet: metadata only (no stored file), not malware-scanned, the FDR is not
              bank-confirmed and verified, or (online deposits) the money rests on the institution's declaration only
"""
from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import documents, pdf, portal_audit, timeline
from .. import models as m
from .. import serialize as S
from ..bank.simulator import BANKS
from ..db import get_db
from ..deps import Principal, current, institution_scope
from ..domain import fdr as fdr_svc
from ..domain.common import fmt_inr
from ..ledger import LEDGER

router = APIRouter(tags=["reports and exports"])

REQUIRED = {
    "FDR": ["fdr_scan", "lien_letter"],
    "FDR_RENEWAL": ["fdr_scan", "lien_letter", "renewal_advice"],
    "ONLINE": ["bank_credit_advice"],
}
LABEL = {**documents.DOC_TYPES, "bank_credit_advice": "Bank credit advice for the deposit (UTR)"}
STATES = ("absent", "expired", "unverified")


def missing_documents(db: Session, inst_id: str | None = None, today: date | None = None) -> list[dict]:
    today = today or date.today()
    k = LEDGER.kernel()
    out: list[dict] = []
    q = select(m.Fdr, m.Institution).join(m.Institution).where(m.Fdr.status.in_(("pending", "verified", "discrepancy")))
    if inst_id:
        q = q.where(m.Fdr.institution_id == inst_id)
    docs_by: dict[str, list[m.FdrDocument]] = {}
    for d in db.scalars(select(m.FdrDocument)):
        docs_by.setdefault(d.fdr_id, []).append(d)
    for f, inst in db.execute(q.order_by(m.Fdr.institution_id, m.Fdr.id)):
        cls = "FDR_RENEWAL" if f.renewal_of else "FDR"
        ins = k.instruments.get(f.instrument_id) or {}
        matured = f.maturity_date < today and not f.renewed_by and ins.get("status") not in ("RENEWED", "RENUMBERED")
        for need in REQUIRED[cls]:
            have = [d for d in docs_by.get(f.id, []) if d.doc_type == need]
            base = {"institution_id": inst.id, "institution": inst.name, "state_of_institution": inst.state, "instrument": f.id, "class": "FDR",
                    "bank": BANKS.get(f.bank, f.bank), "amount": fmt_inr(f.amount_paise), "maturity_date": f.maturity_date.isoformat(),
                    "required": need, "required_label": LABEL[need]}
            if not have:
                out.append({**base, "state": "absent", "detail": "no document of this type on record"})
                continue
            d = max(have, key=lambda x: x.uploaded_on)
            if matured:
                out.append({**base, "state": "expired", "detail": f"the FDR matured on {f.maturity_date.isoformat()} and was not renewed or released"})
            elif not d.stored:
                out.append({**base, "state": "unverified", "detail": "metadata only: no stored file to check"})
            elif d.scan_status != "clean":
                out.append({**base, "state": "unverified", "detail": "not malware-scanned"})
            elif f.status != "verified":
                out.append({**base, "state": "unverified", "detail": f"FDR is {f.status}: not yet bank-confirmed and verified"})
    q2 = select(m.Obligation, m.Institution).join(m.Institution).where(m.Obligation.instrument_class == "ONLINE")
    if inst_id:
        q2 = q2.where(m.Obligation.institution_id == inst_id)
    for o, inst in db.execute(q2.order_by(m.Obligation.institution_id, m.Obligation.obligation_id)):
        if o.obligation_id not in k.obligations:
            continue
        fb = k.funding_breakdown(o.obligation_id)
        proven = fb.get("TRACEABLE", 0) + fb.get("CORROBORATED", 0)
        weak = sum(v for c, v in fb.items() if c not in ("TRACEABLE", "CORROBORATED"))
        if proven >= o.amount_paise:
            continue
        base = {"institution_id": inst.id, "institution": inst.name, "state_of_institution": inst.state, "instrument": o.obligation_id, "class": "ONLINE",
                "bank": "AICTE pool account", "amount": fmt_inr(o.amount_paise), "maturity_date": "", "required": "bank_credit_advice",
                "required_label": LABEL["bank_credit_advice"]}
        if proven == 0 and weak == 0:
            out.append({**base, "state": "absent", "detail": "no bank credit allocated to this deposit"})
        else:
            out.append({**base, "state": "unverified", "detail": f"{fmt_inr(o.amount_paise - proven)} rests on declarations or uncertain sources, not on a bank credit advice"})
    return out


def _scope(p: Principal, institution_id: str) -> str | None:
    if p.user.role == "INSTITUTION":
        return p.user.institution_id
    return institution_id or None


@router.get("/reports/missing-documents")
def report(p: Principal = Depends(current), db: Session = Depends(get_db), institution_id: str = "", state: str = "",
           page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=500)):
    rows = missing_documents(db, _scope(p, institution_id))
    summary = {s: sum(1 for r in rows if r["state"] == s) for s in STATES}
    if state:
        rows = [r for r in rows if r["state"] == state]
    per_inst: dict[str, dict] = {}
    for r in rows:
        g = per_inst.setdefault(r["institution_id"], {"institution_id": r["institution_id"], "institution": r["institution"], "absent": 0, "expired": 0,
                                                      "unverified": 0})
        g[r["state"]] += 1
    return {"as_of": date.today().isoformat(), "required": {c: [{"type": t, "label": LABEL[t]} for t in ts] for c, ts in REQUIRED.items()},
            "summary": summary, "institutions": len(per_inst), "by_institution": sorted(per_inst.values(), key=lambda g: -(g["absent"] + g["expired"] + g["unverified"]))[:100],
            "total": len(rows), "items": rows[(page - 1) * size: page * size],
            "planned": "Bank guarantee (BG) instruments: no document workflow yet (planned)."}


COLS = [("institution", "Institution"), ("instrument", "Instrument"), ("class", "Class"), ("bank", "Bank"), ("amount", "Amount"),
        ("maturity_date", "Maturity"), ("required_label", "Required document"), ("state", "State"), ("detail", "Detail")]


@router.get("/reports/missing-documents.csv")
def report_csv(p: Principal = Depends(current), db: Session = Depends(get_db), institution_id: str = "", state: str = ""):
    rows = [r for r in missing_documents(db, _scope(p, institution_id)) if not state or r["state"] == state]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([c[1] for c in COLS])
    for r in rows:
        w.writerow([r[c[0]] for c in COLS])
    portal_audit.record(db, "report_exported", p.actor, {"report": "missing_documents", "format": "csv", "rows": len(rows)})
    db.commit()
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="missing-documents-{date.today()}.csv"'})


def _pdf_response(data: bytes, name: str) -> Response:
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


def _who(p: Principal) -> str:
    return f"institution:{p.user.institution_id}" if p.user.role == "INSTITUTION" else f"{p.user.role.lower()}:{p.user.kernel_role}"


@router.get("/reports/missing-documents.pdf")
def report_pdf(p: Principal = Depends(current), db: Session = Depends(get_db), institution_id: str = "", state: str = ""):
    all_rows = missing_documents(db, _scope(p, institution_id))
    rows = [r for r in all_rows if not state or r["state"] == state]
    summ = ", ".join(f"{s}: {sum(1 for r in all_rows if r['state'] == s)}" for s in STATES)
    data = pdf.build("Missing documents and exceptions", [("p", f"{len(rows)} items. {summ}."),
                                                          ("table", [c[1] for c in COLS], [[r[c[0]] for c in COLS] for r in rows])],
                     subtitle=f"Required documents per instrument class that are absent, expired or unverified, as of {date.today().isoformat()}",
                     simulated=True, exported_by=_who(p), wide=True)
    portal_audit.record(db, "report_exported", p.actor, {"report": "missing_documents", "format": "pdf", "rows": len(rows)})
    db.commit()
    return _pdf_response(data, f"missing-documents-{date.today()}.pdf")


class TableExportIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    subtitle: str | None = Field(None, max_length=300)
    columns: list[str] = Field(min_length=1, max_length=20)
    rows: list[list[str]] = Field(max_length=5000)
    simulated: bool = False
    note: str | None = Field(None, max_length=500)


@router.post("/exports/pdf")
def export_table(body: TableExportIn, p: Principal = Depends(current), db: Session = Depends(get_db)):
    """PDF of a table exactly as the user sees it (the frontend sends the visible rows), in the print-packet layout."""
    blocks = ([("p", body.note)] if body.note else []) + [("table", body.columns, body.rows)]
    data = pdf.build(body.title, blocks, subtitle=body.subtitle, simulated=body.simulated, exported_by=_who(p), wide=len(body.columns) > 6)
    portal_audit.record(db, "report_exported", p.actor, {"report": body.title[:80], "format": "pdf", "rows": len(body.rows), "simulated": body.simulated})
    db.commit()
    return _pdf_response(data, f"{''.join(ch if ch.isalnum() else '-' for ch in body.title.lower())[:50]}-{pdf.stamp()}.pdf")


@router.get("/fdrs/{fid}/packet.pdf")
def fdr_packet(fid: str, p: Principal = Depends(current), db: Session = Depends(get_db)):
    """The FDR evidence packet: declared vs bank-confirmed, documents with SHA-256 and encryption, timeline with the rules in
    force, observations and ledger events."""
    f = db.get(m.Fdr, fid)
    if not f:
        raise HTTPException(404, "not found")
    institution_scope(p, f.institution_id)
    k = LEDGER.kernel()
    inst = db.get(m.Institution, f.institution_id)
    d = S.fdr(f, inst)
    cmp = fdr_svc.comparison(k, f)
    tl = timeline.fdr_timeline(db, k, f)
    docs = db.scalars(select(m.FdrDocument).where(m.FdrDocument.fdr_id == fid)).all()
    obs = db.scalars(select(m.Observation).where(m.Observation.fdr_id == fid)).all()
    blocks = [
        ("kv", [("Institution", f"{inst.name} ({inst.aicte_id})"), ("FDR reference", f.id), ("Issuing bank", BANKS.get(f.bank, f.bank)),
                ("Instrument number", f.instrument_no), ("Principal", fmt_inr(f.amount_paise)), ("Issue date", f.issue_date.isoformat()),
                ("Maturity date", f.maturity_date.isoformat()), ("Status", f"{d['status']} ({d['bucket']})"), ("PAN (masked)", S.institution(inst)["pan_masked"])]),
        ("h2", "Declared vs confirmed by the issuing bank (SIMULATED bank)"),
        ("table", ["Field", "Declared", "Bank confirmed", "Confidence"], [[r["label"], r["declared"], r["bank_confirmed"] or "—", r["confidence"]] for r in cmp["rows"]]),
        ("h2", "Documents"),
        ("table", ["Type", "Name", "Size", "SHA-256", "At rest", "Scan"],
         [[documents.DOC_TYPES.get(x.doc_type, x.doc_type), x.name, f"{x.size_bytes // 1024} KB", x.sha256,
           f"{x.enc_alg} ({x.kek_id})" if x.enc_alg else ("metadata only" if not x.stored else "—"), x.scan_status] for x in docs]),
        ("h2", "History, with the rules in force on each date"),
        ("table", ["Date", "Event", "Source", "Editions in force", "Rule"],
         [[e["date"], e["label"], e["source"], ", ".join(e["editions_in_force"]) or "none",
           f"{e['rule']['key']}: {e['rule']['status']}" if e.get("rule") else ""] for e in tl["events"]]),
    ]
    if tl["gaps"]:
        blocks += [("h2", "Gaps"), ("table", ["Gap", "Since", "Days"], [[g["label"], g["since"], g["days"]] for g in tl["gaps"]])]
    if obs:
        blocks += [("h2", "Scrutiny observations"), ("table", ["Raised", "Category", "Observation", "Status"],
                                                      [[o.raised_at, o.category, o.text, o.status] for o in obs])]
    kev = db.scalars(select(m.KernelEvent).where(m.KernelEvent.data.like(f'%"{f.obligation_id}"%')).order_by(m.KernelEvent.seq)).all()
    blocks += [("h2", "Ledger events (hash-chained)"), ("table", ["Seq", "At", "Type", "Actor", "Hash"], [[e.seq, e.at, e.type, e.actor, e.hash[:20] + "…"] for e in kev])]
    data = pdf.build(f"FDR evidence packet — {f.id}", blocks, subtitle=f"{inst.name} · {BANKS.get(f.bank, f.bank)} · {f.instrument_no}", simulated=True,
                     exported_by=_who(p), wide=True)
    portal_audit.record(db, "report_exported", p.actor, {"report": "fdr_packet", "fdr_id": fid, "format": "pdf"})
    db.commit()
    return _pdf_response(data, f"{f.id}-evidence-packet.pdf")
