"""Permitted field updates (before/after, user, time, reason, hash-chained) and scrutiny observations."""
from __future__ import annotations

import json

from sqlalchemy import select

from app import crypto
from app import models as m
from app.db import SessionLocal
from conftest import ABC, AUD, AUDITOR, INS, KIRAN, OFF, XYZ


def _pending_fdr(inst="INST0001") -> str:
    with SessionLocal() as db:
        return db.scalars(select(m.Fdr.id).where(m.Fdr.institution_id == inst, m.Fdr.status == "pending")).first()


def test_permitted_change_keeps_before_after_reason_and_is_chained(api):
    a = api().login(ABC, INS)
    r = a.patch("/api/records/institution/INST0001", json={"field": "email", "value": "accounts@abc-eng.edu.in", "reason": "new accounts office"})
    assert r.status_code == 200, r.text
    ch = r.json()["change"]
    assert ch["before"] and ch["after"] == "accounts@abc-eng.edu.in" and ch["actor"] == "institution:INST0001" and ch["reason"] == "new accounts office"
    with SessionLocal() as db:
        ev = db.get(m.PortalEvent, ch["audit_seq"])
        assert ev.type == "field_changed" and json.loads(ev.data)["after"] == "accounts@abc-eng.edu.in"
    v = api().login(AUDITOR, AUD, "totp").post("/api/audit-trail/verify").json()
    assert v["portal_chain"]["valid"]
    hist = a.get("/api/records/institution/INST0001/changes").json()["items"]
    assert [h["field"] for h in hist] == ["email"]


def test_pii_change_is_masked_in_history_and_encrypted_at_rest(api):
    a = api().login(ABC, INS)
    r = a.patch("/api/records/institution/INST0001", json={"field": "registered_mobile", "value": "+919876543210", "reason": "principal changed phone"})
    assert r.status_code == 200, r.text
    ch = r.json()["change"]
    assert ch["after"].endswith("3210") and "98765" not in ch["after"] and "98765" not in (ch["before"] or "")
    with SessionLocal() as db:
        inst = db.get(m.Institution, "INST0001")
        assert crypto.is_encrypted(inst.registered_mobile) and crypto.decrypt_field(inst.registered_mobile) == "+919876543210"
        assert "9876543210" not in db.get(m.PortalEvent, ch["audit_seq"]).data


def test_ledger_fields_roles_and_states_are_enforced(api):
    a = api().login(ABC, INS)
    fid = _pending_fdr()
    assert a.patch(f"/api/records/fdr/{fid}", json={"field": "amount_paise", "value": "1", "reason": "typo in amount"}).status_code == 422
    assert a.patch(f"/api/records/fdr/{fid}", json={"field": "maturity_date", "value": "2030-01-01", "reason": "typo"}).status_code == 422
    assert a.patch("/api/records/institution/INST0001", json={"field": "pan", "value": "AAATA1234B", "reason": "correct pan"}).status_code == 403
    assert a.patch(f"/api/records/fdr/{fid}", json={"field": "branch", "value": "x", "reason": "short branch"}).status_code == 422
    assert a.patch(f"/api/records/fdr/{fid}", json={"field": "branch", "value": "Anna Nagar Branch", "reason": "branch renamed"}).status_code == 200
    with SessionLocal() as db:
        verified = db.scalars(select(m.Fdr.id).where(m.Fdr.institution_id == "INST0001", m.Fdr.status == "verified")).first()
    assert a.patch(f"/api/records/fdr/{verified}", json={"field": "branch", "value": "Other Branch", "reason": "after verification"}).status_code == 409
    assert api().login(XYZ, INS).patch(f"/api/records/fdr/{fid}", json={"field": "branch", "value": "Mine Now", "reason": "not mine"}).status_code == 404
    off = api().login(KIRAN, OFF, "totp")
    assert off.patch("/api/records/institution/INST0001", json={"field": "pan", "value": "AAATA1234B", "reason": "PAN corrected per deed"}).status_code == 200


def test_observation_lifecycle_open_answered_closed(api):
    fid = _pending_fdr()
    off = api().login(KIRAN, OFF, "totp")
    assert api().login(ABC, INS).post(f"/api/fdrs/{fid}/observations", json={"category": "query", "text": "institutions cannot raise"}).status_code == 403
    o = off.post(f"/api/fdrs/{fid}/observations", json={"category": "missing_document", "text": "Lien letter is not signed by the branch manager"}).json()["observation"]
    assert o["status"] == "open" and o["category"] == "missing_document"
    inst = api().login(ABC, INS)
    note = inst.get("/api/nudge/centre").json()["items"][0]
    assert note["template"] == "observation_raised" and fid in note["text"]
    r = inst.post(f"/api/observations/{o['id']}/replies", json={"text": "Signed copy uploaded today"}).json()
    assert r["items"][0]["status"] == "answered" and r["items"][0]["replies"][0]["side"] == "institution"
    assert api().login(XYZ, INS).post(f"/api/observations/{o['id']}/replies", json={"text": "not my FDR"}).status_code == 404
    assert off.post(f"/api/observations/{o['id']}/close").json()["observation"]["status"] == "closed"
    assert inst.post(f"/api/observations/{o['id']}/replies", json={"text": "late reply"}).status_code == 409
    with SessionLocal() as db:
        types = [e.type for e in db.scalars(select(m.PortalEvent).where(m.PortalEvent.type.like("observation_%")))]
    assert types == ["observation_raised", "observation_replied", "observation_closed"]
