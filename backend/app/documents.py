"""Document intake and retrieval.

Upload:  PDF checks (extension, declared MIME, magic bytes, parses, no active content, size) -> malware scan ->
         SHA-256 of the plaintext -> AES-256-GCM envelope encryption -> object store (ciphertext only).
Download: role and institution check -> fetch -> decrypt -> SHA-256 must match the stored value -> audit record.
"""
from __future__ import annotations

import hashlib
import io
import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import crypto, portal_audit
from . import models as m
from .scanner import ScannerUnavailable, scanner
from .storage import store

MAX_BYTES = 10 * 1024 * 1024
MIN_BYTES = 64
PDF_MIME = {"application/pdf", "application/x-pdf"}
DOC_TYPES = {
    "fdr_scan": "Scanned FDR (both sides)",
    "lien_letter": "Bank letter marking lien in favour of AICTE",
    "renewal_advice": "Bank renewal / replacement advice",
    "other": "Other supporting document",
}
# PDF features that run code or carry hidden payloads. Bank and institution letters never need them.
ACTIVE_CONTENT = (b"/JavaScript", b"/JS ", b"/JS(", b"/Launch", b"/EmbeddedFile", b"/RichMedia", b"/XFA")
# Who may read documents. Institutions are additionally limited to their own records (deps.institution_scope).
READ_ROLES = frozenset({"AICTE_OFFICIAL", "AUDITOR", "INSTITUTION"})


CHECK_LABELS = {"size": "Size between 64 bytes and 10 MB", "extension": "File name ends in .pdf", "mime": "Declared type is application/pdf",
                "magic": "Content starts with the PDF signature (%PDF-)", "active_content": "No scripts, attachments or forms",
                "parses": "Opens as an unencrypted PDF with at least one page"}


def run_checks(name: str, content_type: str | None, data: bytes) -> list[dict]:
    """The content checks, in order. Stops at the first failure (later checks are reported as not run).
    Each entry: {code, label, ok (True / False / None = not run), detail, status (HTTP status to refuse with)}."""
    label = name or "document"
    out: list[dict] = []

    def add(code: str, ok: bool | None, detail: str = "", status: int = 422) -> bool:
        out.append({"code": code, "label": CHECK_LABELS[code], "ok": ok, "detail": detail, "status": status})
        return bool(ok)

    def parses() -> tuple[bool, str]:
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                return False, f"{label}: password-protected PDFs cannot be verified; upload an unprotected copy"
            if len(reader.pages) < 1:
                return False, f"{label}: PDF has no pages"
            return True, f"{len(reader.pages)} page(s)"
        except Exception as e:  # noqa: BLE001 - any parser failure means we cannot trust the file
            return False, f"{label}: PDF could not be read ({type(e).__name__})"

    steps = [
        ("size", lambda: (False, f"{label}: larger than 10 MB", 413) if len(data) > MAX_BYTES else
                         (False, f"{label}: file is empty or truncated", 422) if len(data) < MIN_BYTES else (True, f"{len(data)} bytes", 0)),
        ("extension", lambda: (True, "", 0) if label.lower().endswith(".pdf") else (False, f"{label}: only PDF files are accepted", 415)),
        ("mime", lambda: (True, "", 0) if (content_type or "").split(";")[0].strip().lower() in PDF_MIME else
                         (False, f"{label}: declared type {content_type!r} is not application/pdf", 415)),
        ("magic", lambda: (True, "", 0) if data.startswith(b"%PDF-") else
                          (False, f"{label}: content is not a PDF (the file starts with {data[:8]!r})", 415)),
        ("active_content", lambda: (False, f"{label}: PDF contains scripts, attachments or forms; print it to a plain PDF and upload again", 422)
                                   if any(tag in data for tag in ACTIVE_CONTENT) else (True, "", 0)),
        ("parses", lambda: (*parses(), 422)),
    ]
    failed = False
    for code, fn in steps:
        if failed:
            add(code, None, "not run")
            continue
        ok, detail, status = fn()
        if not add(code, ok, detail, status or 422):
            failed = True
    return out


def check_pdf(name: str, content_type: str | None, data: bytes) -> list[dict]:
    """Raises 413/415/422 with a reason the uploader can act on; returns the passed checks otherwise."""
    checks = run_checks(name, content_type, data)
    bad = next((c for c in checks if c["ok"] is False), None)
    if bad:
        raise HTTPException(bad["status"], bad["detail"])
    return [{k: c[k] for k in ("code", "label", "ok", "detail")} for c in checks]


def precheck(db: Session, *, name: str, content_type: str | None, data: bytes, actor: str) -> dict:
    """Runs the same content checks and malware scan as an upload, without storing anything. A malware hit is audited."""
    checks = [{k: c[k] for k in ("code", "label", "ok", "detail")} for c in run_checks(name, content_type, data)]
    digest = hashlib.sha256(data).hexdigest()
    scan: dict = {"status": "not_run", "engine": None, "signature": None}
    if all(c["ok"] for c in checks):
        try:
            res = scanner().scan(data)
            scan = {"status": "clean" if res.clean else "infected", "engine": res.engine, "signature": res.signature}
            if not res.clean:
                portal_audit.record(db, "document_rejected_malware", actor, {"name": name[:160], "sha256": digest, "engine": res.engine,
                                                                            "signature": res.signature, "stage": "precheck"})
                db.commit()
        except ScannerUnavailable:
            scan = {"status": "unavailable", "engine": None, "signature": None}
    return {"name": name, "size": len(data), "sha256": digest, "checks": checks, "scan": scan,
            "accepted": all(c["ok"] for c in checks) and scan["status"] == "clean",
            "encryption": {"alg": "AES-256-GCM", "note": "applied when the FDR is submitted; nothing is stored by this check"}}


def ingest(db: Session, *, name: str, content_type: str | None, data: bytes, doc_type: str, actor: str) -> dict:
    """Validates, scans, encrypts and stores one file. Returns the FdrDocument fields. Infected files are never stored;
    the refusal is audited and committed even though the request fails."""
    if doc_type not in DOC_TYPES:
        raise HTTPException(422, f"unknown document type {doc_type!r}")
    checks = check_pdf(name, content_type, data)
    digest = hashlib.sha256(data).hexdigest()
    try:
        res = scanner().scan(data)
    except ScannerUnavailable as e:
        raise HTTPException(503, "malware scanner unavailable; the document was not stored, try again shortly") from e
    if not res.clean:
        portal_audit.record(db, "document_rejected_malware", actor, {"name": name[:160], "sha256": digest, "engine": res.engine,
                                                                    "signature": res.signature})
        db.commit()
        raise HTTPException(422, f"{name}: rejected by the malware scan ({res.signature})")
    key = f"docs/{digest[:2]}/{uuid.uuid4().hex}"
    sealed = crypto.seal_document(data, key)
    try:
        st = store()
        st.put(key, sealed.ciphertext)
    except Exception as e:  # noqa: BLE001 - any object-store failure: refuse clearly, store nothing
        raise HTTPException(503, "document store unavailable; nothing was stored, try again shortly") from e
    return {"name": (name or "document.pdf")[:160], "size": len(data), "sha256": digest, "stored": True, "doc_type": doc_type,
            "uploaded_by": actor, "object_key": key, "store_name": st.name, "enc_alg": sealed.alg, "kek_id": sealed.kek_id,
            "wrapped_dek": sealed.wrapped_dek, "nonce": sealed.nonce, "scan_status": "clean", "scan_engine": res.engine,
            "scanned_at": res.scanned_at, "content_checks": checks}


def add_row(db: Session, fdr_id: str, meta: dict, at: datetime) -> m.FdrDocument:
    row = m.FdrDocument(fdr_id=fdr_id, uploaded_on=at, **{k: v for k, v in meta.items() if k not in ("size",)}, size_bytes=meta["size"])
    db.add(row)
    return row


def read(db: Session, doc: m.FdrDocument, actor: str, role: str) -> bytes:
    """Decrypts and integrity-checks one stored document, and audits the access."""
    if role not in READ_ROLES:
        raise HTTPException(403, "your role cannot read documents")
    if not doc.stored or not doc.object_key:
        raise HTTPException(404, "seeded record: metadata only, no file stored")
    try:
        blob = store().get(doc.object_key)
        data = crypto.open_document(blob, doc.wrapped_dek or "", doc.nonce or "", doc.object_key)
    except Exception as e:  # noqa: BLE001 - missing object, wrong key or tampered ciphertext all mean: do not serve
        portal_audit.record(db, "document_integrity_failure", actor, {"document_id": doc.id, "fdr_id": doc.fdr_id, "stage": "decrypt",
                                                                     "error": type(e).__name__})
        db.commit()
        raise HTTPException(500, "stored document could not be decrypted; the incident has been recorded") from e
    if hashlib.sha256(data).hexdigest() != doc.sha256:
        portal_audit.record(db, "document_integrity_failure", actor, {"document_id": doc.id, "fdr_id": doc.fdr_id, "stage": "checksum"})
        db.commit()
        raise HTTPException(500, "stored document failed its SHA-256 check; the incident has been recorded")
    portal_audit.record(db, "document_downloaded", actor, {"document_id": doc.id, "fdr_id": doc.fdr_id, "sha256": doc.sha256, "role": role})
    db.commit()
    return data


def verify_integrity(db: Session, doc: m.FdrDocument, actor: str, role: str) -> dict:
    """Fetches, decrypts and re-hashes a stored document without serving it; records the result on the row and in the audit."""
    if role not in READ_ROLES:
        raise HTTPException(403, "your role cannot read documents")
    if not doc.stored or not doc.object_key:
        raise HTTPException(409, "seeded record: metadata only, no file stored, nothing to check")
    at = datetime.now().isoformat(timespec="seconds")
    try:
        data = crypto.open_document(store().get(doc.object_key), doc.wrapped_dek or "", doc.nonce or "", doc.object_key)
        actual = hashlib.sha256(data).hexdigest()
        status = "match" if actual == doc.sha256 else "mismatch"
    except Exception as e:  # noqa: BLE001 - missing object, wrong key or tampered ciphertext
        actual, status = None, f"unreadable:{type(e).__name__}"[:40]
    doc.integrity_status, doc.integrity_checked_at = status, at
    portal_audit.record(db, "document_integrity_checked" if status == "match" else "document_integrity_failure", actor,
                        {"document_id": doc.id, "fdr_id": doc.fdr_id, "expected": doc.sha256, "actual": actual, "result": status, "stage": "verify"}, at=at)
    db.commit()
    return {"document_id": doc.id, "expected": doc.sha256, "actual": actual, "result": status, "checked_at": at}


def describe(d: m.FdrDocument) -> dict:
    return {"id": d.id, "name": d.name, "size_bytes": d.size_bytes, "sha256": d.sha256, "uploaded_on": d.uploaded_on.isoformat(),
            "stored": d.stored, "doc_type": d.doc_type, "doc_type_label": DOC_TYPES.get(d.doc_type, d.doc_type),
            "encryption": ({"alg": d.enc_alg, "kek_id": d.kek_id, "store": d.store_name} if d.enc_alg else None),
            "scan": {"status": d.scan_status, "engine": d.scan_engine, "at": d.scanned_at},
            "content_checks": d.content_checks or [], "integrity": {"status": d.integrity_status, "at": d.integrity_checked_at}}
