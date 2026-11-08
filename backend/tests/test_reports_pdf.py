"""Missing-documents report (absent / expired / unverified, CSV and PDF) and PDF export in the packet layout."""
from __future__ import annotations

import io
from datetime import date, timedelta

from pypdf import PdfReader
from sqlalchemy import select

from app import models as m
from app.db import SessionLocal
from conftest import ABC, INS, MEERA, OFF, XYZ


def _text(data: bytes) -> str:
    r = PdfReader(io.BytesIO(data))
    return "\n".join(p.extract_text() for p in r.pages), len(r.pages)


def test_missing_documents_finds_absent_expired_and_unverified(api):
    with SessionLocal() as db:
        f = db.scalars(select(m.Fdr).where(m.Fdr.status == "verified", m.Fdr.renewed_by.is_(None)).order_by(m.Fdr.id)).first()
        f.maturity_date = date.today() - timedelta(days=20)
        lien_missing = db.scalars(select(m.Fdr.id).where(m.Fdr.status.in_(("pending", "verified", "discrepancy")),
                                                       ~m.Fdr.id.in_(select(m.FdrDocument.fdr_id).where(m.FdrDocument.doc_type == "lien_letter")))).all()
        db.commit()
        expired_id = f.id
    assert lien_missing, "seed should contain FDRs filed without a lien letter"
    r = api().login(MEERA, OFF, "totp").get("/api/reports/missing-documents?size=500").json()
    assert r["summary"]["absent"] >= len(lien_missing) and r["summary"]["expired"] >= 1 and r["summary"]["unverified"] >= 1
    got = {(i["instrument"], i["required"], i["state"]) for i in r["items"]}
    assert (lien_missing[0], "lien_letter", "absent") in got
    assert (expired_id, "fdr_scan", "expired") in got
    assert any(c == "ONLINE" for c in (i["class"] for i in r["items"])) or "ONLINE" in r["required"]
    assert r["by_institution"][0]["absent"] + r["by_institution"][0]["expired"] + r["by_institution"][0]["unverified"] >= 1


def test_missing_documents_is_scoped_for_institutions(api):
    mine = api().login(ABC, INS).get("/api/reports/missing-documents?institution_id=INST0002&size=500").json()
    assert all(i["institution_id"] == "INST0001" for i in mine["items"])


def test_missing_documents_csv_and_pdf(api):
    a = api().login(MEERA, OFF, "totp")
    c = a.get("/api/reports/missing-documents.csv?state=absent")
    assert c.status_code == 200 and c.headers["content-type"].startswith("text/csv")
    lines = c.text.lstrip("﻿").splitlines()
    assert lines[0].startswith("Institution,Instrument") and all(",absent," in ln for ln in lines[1:])
    p = a.get("/api/reports/missing-documents.pdf?state=absent")
    assert p.status_code == 200 and p.content.startswith(b"%PDF")
    text, pages = _text(p.content)
    assert "Missing documents and exceptions" in text and "SIMULATED bank data" in text and "All India Council for Technical Education" in text
    assert f"of {pages}" in text and "Exported by aicte_official:deputy_director" in text


def test_any_table_exports_to_pdf_with_simulated_label(api):
    a = api().login(ABC, INS)
    rows = [[f"FDR2026{i:05d}", "State Bank of India", "Rs 25,00,000", "Active"] for i in range(120)]
    p = a.post("/api/exports/pdf", json={"title": "My FDRs", "columns": ["FDR", "Bank", "Amount", "Status"], "rows": rows, "simulated": True})
    assert p.status_code == 200
    text, pages = _text(p.content)
    assert pages >= 2 and "FDR202600119" in text and "SIMULATED bank data" in text and text.count("NIDHIVEDA") >= pages
    plain = a.post("/api/exports/pdf", json={"title": "Messages", "columns": ["At", "Text"], "rows": [["today", "hello"]], "simulated": False})
    assert "SIMULATED bank data" not in _text(plain.content)[0]


def test_fdr_evidence_packet_pdf(api):
    a = api().login(ABC, INS)
    fid = a.get("/api/fdrs?size=1").json()["items"][0]["id"]
    p = a.get(f"/api/fdrs/{fid}/packet.pdf")
    assert p.status_code == 200
    text, _ = _text(p.content)
    for s in (f"FDR evidence packet", fid, "Declared vs confirmed", "SHA-256", "rules in force", "Ledger events", "SIMULATED bank data"):
        assert s in text, s
    other = api().login(XYZ, INS).get(f"/api/fdrs/{fid}/packet.pdf")
    assert other.status_code == 404
