"""Documents: PDF-only intake, malware scan, envelope encryption at rest, SHA-256 on download, audited access.
PII: a stolen database file shows no plaintext PAN, bank account or registered mobile."""
from __future__ import annotations

import io
import re
import sqlite3
from datetime import date, timedelta

import pytest
from reportlab.pdfgen import canvas
from sqlalchemy import select

from app import crypto
from app import models as m
from app.config import get_settings
from app.db import SessionLocal
from app.scanner import EICAR
from app.storage import store
from conftest import ABC, AUD, AUDITOR, INS, MEERA, OFF, XYZ

MARKER = "TL-PLAINTEXT-MARKER-7f3a"


def pdf(text: str = MARKER, extra: bytes = b"", trailer: bytes = b"") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pageCompression=0)
    c.drawString(72, 720, text)
    c.save()
    data = buf.getvalue()
    if extra:
        data = data.replace(b"%%EOF", extra + b"\n%%EOF")
    return data + trailer


def _form(no: str) -> dict:
    issue = date.today() - timedelta(days=10)
    return {"bank": "SBI", "branch": "Chennai Main", "instrument_no": no, "amount_rupees": "2500000", "rate_bp": "700",
            "issue_date": issue.isoformat(), "maturity_date": (issue + timedelta(days=3 * 365 + 2)).isoformat()}


def _upload(a, no: str, files: list[tuple[str, bytes, str]]):
    return a.post("/api/fdrs", data=_form(no), files=[("files", f) for f in files])


@pytest.fixture()
def fresh_store(tmp_path):
    get_settings().object_dir = str(tmp_path / "objects")
    store.cache_clear()
    yield tmp_path / "objects"
    store.cache_clear()


def test_upload_encrypts_stores_and_verifies_on_download(api, fresh_store):
    a = api().login(ABC, INS)
    r = _upload(a, "SBI-DOC-0001", [("fdr.pdf", pdf(), "application/pdf"), ("lien.pdf", pdf("lien letter"), "application/pdf")])
    assert r.status_code == 200, r.text
    docs = r.json()["documents"]
    assert [d["doc_type"] for d in docs] == ["fdr_scan", "lien_letter"]
    assert all(d["encryption"]["alg"] == crypto.DOC_ALG and d["scan"]["status"] == "clean" for d in docs)
    # on disk: ciphertext only
    blobs = [p.read_bytes() for p in fresh_store.rglob("*") if p.is_file()]
    assert len(blobs) == 2 and all(MARKER.encode() not in b and not b.startswith(b"%PDF") for b in blobs)
    fid = r.json()["fdr"]["id"]
    got = a.get(f"/api/fdrs/{fid}/documents/{docs[0]['id']}")
    assert got.status_code == 200 and got.content.startswith(b"%PDF") and MARKER.encode() in got.content
    assert got.headers["x-document-sha256"] == docs[0]["sha256"]
    with SessionLocal() as db:
        ev = db.scalars(select(m.PortalEvent).where(m.PortalEvent.type == "document_downloaded")).all()
        assert ev and ev[-1].actor.startswith("institution:")


def test_document_bytes_unreadable_without_the_key(api, fresh_store):
    a = api().login(ABC, INS)
    r = _upload(a, "SBI-DOC-0002", [("fdr.pdf", pdf(), "application/pdf"), ("lien.pdf", pdf(), "application/pdf")])
    doc = r.json()["documents"][0]
    with SessionLocal() as db:
        row = db.get(m.FdrDocument, doc["id"])
        blob = store().get(row.object_key)
        wrong = crypto.LocalKms(b"\x01" * 32)
        with pytest.raises(Exception):   # wrong KEK cannot unwrap the data key
            wrong.unwrap(__import__("base64").b64decode(row.wrapped_dek), row.object_key.encode())
        assert crypto.open_document(blob, row.wrapped_dek, row.nonce, row.object_key).startswith(b"%PDF")
        with pytest.raises(Exception):   # ciphertext moved to another object key fails authentication
            crypto.open_document(blob, row.wrapped_dek, row.nonce, "docs/xx/other")


def test_tampered_ciphertext_is_refused_and_audited(api, fresh_store):
    a = api().login(ABC, INS)
    r = _upload(a, "SBI-DOC-0003", [("fdr.pdf", pdf(), "application/pdf"), ("lien.pdf", pdf(), "application/pdf")])
    fid, doc = r.json()["fdr"]["id"], r.json()["documents"][0]
    with SessionLocal() as db:
        key = db.get(m.FdrDocument, doc["id"]).object_key
    blob = bytearray(store().get(key))
    blob[40] ^= 0xFF
    store().put(key, bytes(blob))
    assert a.get(f"/api/fdrs/{fid}/documents/{doc['id']}").status_code == 500
    with SessionLocal() as db:
        assert db.scalars(select(m.PortalEvent).where(m.PortalEvent.type == "document_integrity_failure")).first()


@pytest.mark.parametrize("name,data,mime,status", [
    ("fdr.jpg", b"\xff\xd8\xff" + b"0" * 200, "image/jpeg", 415),               # not a PDF
    ("fdr.pdf", b"\x89PNG\r\n\x1a\n" + b"0" * 200, "application/pdf", 415),     # PDF name, PNG bytes
    ("fdr.pdf", pdf(), "text/plain", 415),                                       # wrong declared MIME
    ("fdr.pdf", b"%PDF-1.4\n" + b"garbage" * 40, "application/pdf", 422),       # does not parse
    ("fdr.pdf", pdf(extra=b"/JavaScript (app.alert(1))"), "application/pdf", 422),  # active content
    ("fdr.pdf", b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024), "application/pdf", 413),  # over 10 MB
])
def test_upload_rejects_non_pdf_and_unsafe_pdf(api, fresh_store, name, data, mime, status):
    a = api().login(ABC, INS)
    r = _upload(a, "SBI-DOC-0004", [(name, data, mime), ("lien.pdf", pdf(), "application/pdf")])
    assert r.status_code == status, r.text
    assert not [p for p in fresh_store.rglob("*") if p.is_file()]


def test_malware_is_rejected_not_stored_and_audited(api, fresh_store):
    a = api().login(ABC, INS)
    r = _upload(a, "SBI-DOC-0005", [("fdr.pdf", pdf(trailer=b"\n" + EICAR + b"\n"), "application/pdf"), ("lien.pdf", pdf(), "application/pdf")])
    assert r.status_code == 422 and "malware" in r.text
    assert not [p for p in fresh_store.rglob("*") if p.is_file()]
    with SessionLocal() as db:
        assert db.scalars(select(m.PortalEvent).where(m.PortalEvent.type == "document_rejected_malware")).first()
        assert not db.scalars(select(m.Fdr).where(m.Fdr.instrument_no == "SBI-DOC-0005")).first()


def test_document_access_is_scoped_per_institution(api, fresh_store):
    a = api().login(ABC, INS)
    r = _upload(a, "SBI-DOC-0006", [("fdr.pdf", pdf(), "application/pdf"), ("lien.pdf", pdf(), "application/pdf")])
    fid, doc = r.json()["fdr"]["id"], r.json()["documents"][0]["id"]
    assert api().login(XYZ, INS).get(f"/api/fdrs/{fid}/documents/{doc}").status_code == 404     # other institution
    assert api().login(MEERA, OFF, "totp").get(f"/api/fdrs/{fid}/documents/{doc}").status_code == 200
    assert api().login(AUDITOR, AUD, "totp").get(f"/api/fdrs/{fid}/documents/{doc}").status_code == 200
    with SessionLocal() as db:
        roles = [__import__("json").loads(e.data)["role"] for e in db.scalars(select(m.PortalEvent).where(m.PortalEvent.type == "document_downloaded"))]
    assert roles == ["AICTE_OFFICIAL", "AUDITOR"]


def test_stolen_database_file_has_no_plaintext_pii(api, db_path):
    """Reads the raw SQLite file and a full SQL dump: no account number, PAN or registered mobile in clear text."""
    from app.ledger import LEDGER
    k = LEDGER.kernel()
    accounts = {p["account"] for p in k.payees.values()} | {a for i in k.institutions.values() for a in i["known_accounts"]}
    accounts = {a for a in accounts if a and a != "UNKNOWN-0000"}
    with SessionLocal() as db:
        insts = db.scalars(select(m.Institution).limit(50)).all()
        pans = {crypto.decrypt_field(i.pan) for i in insts}
        mobiles = {crypto.decrypt_field(i.registered_mobile) for i in insts}
    assert len(accounts) >= 5 and all(re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", p) for p in pans)
    from app.db import engine
    if engine().dialect.name == "postgresql":
        import os
        import subprocess
        url = engine().url
        command = ["docker", "exec", os.environ["TL_TEST_PG_CONTAINER"], "pg_dump", "-U", url.username, "-d", url.database]
        raw = subprocess.check_output([*command, "--format=custom"])
        dump = subprocess.check_output([*command, "--format=plain"], text=True)
    else:
        raw = db_path.read_bytes()
        con = sqlite3.connect(db_path)
        dump = "\n".join(con.iterdump())
        con.close()
    for secret in accounts | pans | mobiles:
        assert secret.encode() not in raw, secret
        assert secret not in dump, secret
    # and the API shows masked values only
    r = api().login(MEERA, OFF, "totp").get("/api/institutions/INST0001").json()["institution"]
    assert r["pan_masked"].endswith(crypto.decrypt_field(insts[0].pan)[-4:]) and r["pan_masked"].startswith("•")


def test_bank_accounts_masked_in_audit_trail_and_bank_log(api):
    a = api().login(AUDITOR, AUD, "totp")
    items = a.get("/api/audit-trail?chain=kernel&q=payee_registered&size=5").json()["items"]
    assert items and all(i["data"]["account"].startswith("•") for i in items)
    msgs = a.get("/api/bank/messages?kind=name_lookup").json()
    rows = msgs["items"] if isinstance(msgs, dict) else msgs
    assert rows and all(r["payload"]["account"].startswith("•") for r in rows if "account" in r["payload"])
