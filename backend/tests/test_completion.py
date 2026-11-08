"""Completion work: per-file content checks and pre-upload scan, SHA-256 re-check of stored documents, policy editor
(before/after in the hash chain, AICTE approving roles only), "what changed" links that exist for each role."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app import models as m
from app import portal_audit
from app.config import get_settings
from app.db import SessionLocal
from app.scanner import EICAR
from app.storage import store
from conftest import ABC, AUD, AUDITOR, INS, KIRAN, MEERA, OFF
from test_documents_security import _upload, pdf

CODES = ["size", "extension", "mime", "magic", "active_content", "parses"]


@pytest.fixture()
def fresh_store(tmp_path):
    get_settings().object_dir = str(tmp_path / "objects")
    store.cache_clear()
    yield tmp_path / "objects"
    store.cache_clear()


def test_precheck_reports_every_check_and_the_scan_without_storing(api, fresh_store):
    a = api().login(ABC, INS)
    r = a.post("/api/documents/precheck", files={"file": ("fdr.pdf", pdf(), "application/pdf")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [c["code"] for c in body["checks"]] == CODES and all(c["ok"] for c in body["checks"])
    assert body["scan"]["status"] == "clean" and body["accepted"] is True and len(body["sha256"]) == 64
    assert not [p for p in fresh_store.rglob("*") if p.is_file()]  # nothing stored

    png = a.post("/api/documents/precheck", files={"file": ("scan.png", b"\x89PNG\r\n\x1a\n" + b"0" * 200, "image/png")}).json()
    oks = {c["code"]: c["ok"] for c in png["checks"]}
    assert oks["size"] is True and oks["extension"] is False and oks["mime"] is None and png["accepted"] is False
    assert png["scan"]["status"] == "not_run"


def test_precheck_flags_malware_and_audits_it(api, fresh_store):
    a = api().login(ABC, INS)
    body = a.post("/api/documents/precheck", files={"file": ("x.pdf", pdf(trailer=b"\n" + EICAR + b"\n"), "application/pdf")}).json()
    assert body["scan"]["status"] == "infected" and body["accepted"] is False
    with SessionLocal() as db:
        ev = db.scalars(select(m.PortalEvent).where(m.PortalEvent.type == "document_rejected_malware")).all()
        assert ev and json.loads(ev[-1].data)["stage"] == "precheck"


def test_precheck_is_for_institutions_only(api):
    off = api().login(MEERA, OFF, "totp")
    assert off.post("/api/documents/precheck", files={"file": ("fdr.pdf", pdf(), "application/pdf")}).status_code == 403


def test_upload_keeps_content_checks_and_sha256_recheck_detects_tampering(api, fresh_store):
    a = api().login(ABC, INS)
    r = _upload(a, "SBI-CHK-0001", [("fdr.pdf", pdf(), "application/pdf"), ("lien.pdf", pdf("lien"), "application/pdf")])
    assert r.status_code == 200, r.text
    fid, doc = r.json()["fdr"]["id"], r.json()["documents"][0]
    assert [c["code"] for c in doc["content_checks"]] == CODES and all(c["ok"] for c in doc["content_checks"])
    assert doc["integrity"]["status"] is None

    ok = a.post(f"/api/fdrs/{fid}/documents/{doc['id']}/verify").json()
    assert ok["result"] == "match" and ok["actual"] == ok["expected"] == doc["sha256"]
    assert ok["document"]["integrity"]["status"] == "match"

    with SessionLocal() as db:   # replace the stored ciphertext with garbage
        key = db.get(m.FdrDocument, doc["id"]).object_key
    store().put(key, b"\x00" * 64)
    bad = a.post(f"/api/fdrs/{fid}/documents/{doc['id']}/verify").json()
    assert bad["result"].startswith("unreadable") and bad["actual"] is None
    with SessionLocal() as db:
        types = [e.type for e in db.scalars(select(m.PortalEvent).order_by(m.PortalEvent.seq))]
        assert "document_integrity_checked" in types and types[-1] == "document_integrity_failure"


def test_sha256_recheck_is_scoped_to_the_institution(api, fresh_store):
    a = api().login(ABC, INS)
    r = _upload(a, "SBI-CHK-0002", [("fdr.pdf", pdf(), "application/pdf"), ("lien.pdf", pdf("lien"), "application/pdf")])
    fid, doc = r.json()["fdr"]["id"], r.json()["documents"][0]
    other = api().login("1-xyz-demo", INS)
    assert other.post(f"/api/fdrs/{fid}/documents/{doc['id']}/verify").status_code == 404
    aud = api().login(AUDITOR, AUD, "totp")
    assert aud.post(f"/api/fdrs/{fid}/documents/{doc['id']}/verify").json()["result"] == "match"


def test_changes_diff_is_leaf_level():
    old = {"a": {"b": 1, "c": [1, 2]}, "d": "x"}
    new = {"a": {"b": 2, "c": [1, 2]}, "d": "x", "e": True}
    assert portal_audit.changes(old, new) == [{"path": "a.b", "before": 1, "after": 2}, {"path": "e", "before": None, "after": True}]


def test_policy_editor_records_before_after_in_the_chain_and_only_approvers_edit(api):
    meera = api().login(MEERA, OFF, "totp")    # deputy director
    cur = meera.get("/api/policy").json()
    assert cur["editable"] is True
    new = json.loads(json.dumps(cur["active"]))
    before = new["payments"]["reissue_target_working_days"]
    new["payments"]["reissue_target_working_days"] = before + 2

    kiran = api().login(KIRAN, OFF, "totp")    # section officer: AICTE, but not an approving role
    assert kiran.get("/api/policy").json()["editable"] is False
    assert kiran.put("/api/policy", json={"policy": new, "reason": "trying without the role"}).status_code == 403
    aud = api().login(AUDITOR, AUD, "totp")
    assert aud.put("/api/policy", json={"policy": new, "reason": "auditors cannot edit policy"}).status_code == 403
    ins = api().login(ABC, INS)
    assert ins.put("/api/policy", json={"policy": new, "reason": "institutions cannot edit policy"}).status_code == 403

    assert meera.put("/api/policy", json={"policy": new, "reason": "short"}).status_code == 422          # reason required (10+)
    assert meera.put("/api/policy", json={"policy": cur["active"], "reason": "no change at all here"}).status_code == 409
    retyped = json.loads(json.dumps(new))
    retyped["payments"]["reissue_target_working_days"] = "seven"
    assert meera.put("/api/policy", json={"policy": retyped, "reason": "wrong type of value"}).status_code == 422

    r = meera.put("/api/policy", json={"policy": new, "reason": "circular AICTE/2026/31: re-issue target"})
    assert r.status_code == 200, r.text
    hist = meera.get("/api/policy/changes").json()["items"]
    top = hist[0]
    assert top["policy"] == "release" and top["reason"].startswith("circular")
    assert top["changes"] == [{"path": "payments.reissue_target_working_days", "before": before, "after": before + 2}]
    with SessionLocal() as db:
        ev = db.scalars(select(m.PortalEvent).where(m.PortalEvent.seq == top["seq"])).one()
        assert ev.type == "policy_changed" and ev.hash == top["hash"]
    assert meera.post("/api/audit-trail/verify").json()["portal_chain"]["valid"] is True


def test_notification_policy_change_carries_before_after(api):
    off = api().login(MEERA, OFF, "totp")
    cur = off.get("/api/nudge/policy").json()["policy"]
    new = json.loads(json.dumps(cur))
    new["ladder"]["action_needed_within_days"] = cur["ladder"]["action_needed_within_days"] + 5
    assert off.put("/api/nudge/policy", json={"policy": cur, "reason": "nothing changes here"}).status_code == 409
    assert off.put("/api/nudge/policy", json={"policy": new, "reason": "longer action window"}).status_code == 200
    top = off.get("/api/policy/changes").json()["items"][0]
    assert top["policy"] == "notification" and top["changes"] == [
        {"path": "ladder.action_needed_within_days", "before": cur["ladder"]["action_needed_within_days"], "after": new["ladder"]["action_needed_within_days"]}]


def test_what_changed_links_point_at_pages_each_role_has(api):
    ins = api().login(ABC, INS)
    w = ins.get("/api/nudge/what-changed?since=2000-01-01T00:00:00").json()
    institution_pages = {"", "profile", "fdrs", "upload", "renewals", "release", "payments", "notifications", "communication", "guidelines",
                         "help", "missing-documents"}
    for item in w["items"]:
        assert item["link"].startswith("/institution/") and item["link"].split("/", 2)[2] in institution_pages, item


def test_object_store_failure_is_a_clear_503_and_stores_nothing(api, fresh_store, monkeypatch):
    from app import documents

    class Down:
        name = "s3"

        def put(self, key, data):
            raise ConnectionError("object store down")
    monkeypatch.setattr(documents, "store", lambda: Down())
    a = api().login(ABC, INS)
    with SessionLocal() as db:
        before = db.query(m.Fdr).count()
    r = _upload(a, "SBI-CHK-0503", [("fdr.pdf", pdf(), "application/pdf"), ("lien.pdf", pdf("lien"), "application/pdf")])
    assert r.status_code == 503 and "nothing was stored" in r.text
    with SessionLocal() as db:
        assert db.query(m.Fdr).count() == before
