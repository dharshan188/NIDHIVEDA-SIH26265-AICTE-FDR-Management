"""Simulated bank layer (signatures, registry, receipt-time validity) and the payment lifecycle (S01 live)."""
from __future__ import annotations

from datetime import datetime, timedelta

from conftest import ANIL, AUD, AUDITOR, INS, KIRAN, MEERA, OFF, RAVI, XYZ

from app.ledger import LEDGER

HDFC_FDR = "FDR202600126"     # ABC's pending HDFC FDR (bank book matches)
SBI_FDR = "FDR202600125"


def _inject(a, **kw):
    return a.post("/api/sim/bank/inject", json=kw).json()


def _conf_payload(fid):
    f = LEDGER.kernel().instruments[f"INS-{fid}"]
    return {"instrument_no": f["number"], "as_of": datetime.now().date().isoformat(), "status": "ACTIVE", "lien_holder": "AICTE",
            "amount": f["amount"], "maturity_date": f["maturity_date"]}


# ------------------------------------------------------------------ signatures and registry
def test_every_bank_message_is_flagged_simulated(api):
    a = api().login(MEERA, OFF)
    r = a.post(f"/api/fdrs/{HDFC_FDR}/bank-confirmation").json()
    assert r["message"]["status"] == "ACCEPTED" and r["message"]["simulated"] is True
    msgs = a.get("/api/bank/messages?size=50").json()
    assert msgs["simulated"] is True and all(x["simulated"] and x["payload"]["simulated"] for x in msgs["items"])


def test_valid_confirmation_then_verify(api):
    a = api().login(MEERA, OFF)
    assert a.post(f"/api/fdrs/{HDFC_FDR}/verify", json={}).status_code == 409   # no bank confirmation yet
    a.post(f"/api/fdrs/{HDFC_FDR}/bank-confirmation")
    d = a.get(f"/api/fdrs/{HDFC_FDR}").json()
    assert {r["confidence"] for r in d["comparison"]["rows"]} == {"BANK_CONFIRMED"}
    assert a.post(f"/api/fdrs/{HDFC_FDR}/verify", json={"note": "ok"}).json()["fdr"]["status"] == "verified"


def test_tampered_message_rejected(api):
    a = api().login(MEERA, OFF)
    out = _inject(a, bank="HDFC", kind="instrument_confirmation", payload=_conf_payload(HDFC_FDR), tamper_payload={"amount": 1})
    assert out["status"] == "REJECTED" and "signature" in out["reason"]


def test_wrong_bank_cannot_confirm_another_banks_fdr(api):
    a = api().login(MEERA, OFF)
    out = _inject(a, bank="SBI", kind="instrument_confirmation", payload=_conf_payload(HDFC_FDR))   # SBI key, HDFC instrument
    assert out["status"] == "REJECTED" and "issuing bank" in out["reason"]


def test_key_of_other_bank_rejected(api):
    a = api().login(MEERA, OFF)
    out = _inject(a, bank="HDFC", key_id="SBI-K1", kind="instrument_confirmation", payload=_conf_payload(HDFC_FDR))
    assert out["status"] == "REJECTED"


def test_unknown_signer_rejected(api):
    a = api().login(MEERA, OFF)
    out = _inject(a, bank="HDFC", key_id="HDFC-K9", kind="instrument_confirmation", payload=_conf_payload(HDFC_FDR))
    assert out["status"] == "REJECTED" and out["reason"] == "unknown signer"


def test_ended_signer_earlier_evidence_stays_valid(api):
    a = api().login(MEERA, OFF)
    assert a.get(f"/api/fdrs/{SBI_FDR}").json()["fdr"]["status"] == "verified"
    a.post("/api/sim/keys/SBI-K1/expire", json={"at": (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")})
    # evidence received before the end of authority is still valid
    assert a.get(f"/api/fdrs/{SBI_FDR}").json()["fdr"]["status"] == "verified"
    # new messages with the ended key are refused; the rotated key works
    out = _inject(a, bank="SBI", key_id="SBI-K1", kind="instrument_confirmation", payload=_conf_payload(SBI_FDR))
    assert out["status"] == "REJECTED" and "ended" in out["reason"]
    out = _inject(a, bank="SBI", key_id="SBI-K2", kind="instrument_confirmation", payload=_conf_payload(SBI_FDR))
    assert out["status"] == "ACCEPTED"


def test_compromised_from_invalidates_evidence_received_after(api):
    a = api().login(MEERA, OFF)
    k = LEDGER.kernel()
    ev = k.evidence[k.instruments[f"INS-{SBI_FDR}"]["confirmations"][0]["evidence_id"]]
    # compromised from just before that confirmation was received: it no longer counts
    a.post("/api/sim/keys/SBI-K1/compromise", json={"at": ev["received_at"]})
    d = a.get(f"/api/fdrs/{SBI_FDR}").json()
    assert d["fdr"]["status"] == "pending"
    assert {r["confidence"] for r in d["comparison"]["rows"]} == {"UNVERIFIED_SOURCE"}


def test_backdating_does_not_escape_compromise(api):
    a = api().login(MEERA, OFF)
    a.post("/api/sim/keys/HDFC-K1/compromise", json={"at": (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")})
    old = (datetime.now() - timedelta(days=30)).isoformat(timespec="seconds")
    out = _inject(a, bank="HDFC", key_id="HDFC-K1", kind="instrument_confirmation", payload=_conf_payload(HDFC_FDR), signed_at=old)
    assert out["status"] == "REJECTED" and "compromised" in out["reason"]   # judged at receipt time, not signed_at


def test_bank_mismatch_creates_discrepancy(api):
    a = api().login(MEERA, OFF)
    p = _conf_payload(HDFC_FDR)
    p["amount"] -= 100_000_00
    assert _inject(a, bank="HDFC", kind="instrument_confirmation", payload=p)["status"] == "ACCEPTED"
    d = a.get(f"/api/fdrs/{HDFC_FDR}").json()
    assert d["fdr"]["status"] == "discrepancy"
    assert any(r["confidence"] == "MISMATCH" and r["field"] == "amount" for r in d["comparison"]["rows"])
    assert a.post(f"/api/fdrs/{HDFC_FDR}/verify", json={}).status_code == 409


def test_identical_redelivery_is_noop_and_changed_content_rejected(api):
    a = api().login(MEERA, OFF)
    p = _conf_payload(HDFC_FDR)
    assert _inject(a, bank="HDFC", kind="instrument_confirmation", payload=p, evidence_id="E-X1")["status"] == "ACCEPTED"
    assert _inject(a, bank="HDFC", kind="instrument_confirmation", payload={**p, "as_of": "2026-01-01"}, evidence_id="E-X1")["status"] == "REJECTED"


# ------------------------------------------------------------------ payment lifecycle, S01 through the live API
def _release_online(api, oid="ONL-XYZ-UG"):
    xyz = api().login(XYZ, INS)
    r = xyz.post("/api/release-requests", json={"obligation_id": oid, "reason": "Programme closure approved; refund requested"})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    kiran = api().login(KIRAN, OFF)
    # entitlement and affidavit were already recorded by kiran in the seed; record them again for this request
    assert kiran.post(f"/api/release-requests/{rid}/scrutiny", json={"entitlement_basis": "Closure approved (EoA 2026-27)"}).status_code == 200
    meera = api().login(MEERA, OFF)
    gate = meera.get(f"/api/release-requests/{rid}/gate").json()
    assert gate["allowed"], gate
    sig = meera.dsc(MEERA, gate["approval_message"])
    r = meera.post(f"/api/release-requests/{rid}/approve", json={"certificate_pem": sig["certificate_pem"], "signature_b64": sig["signature_b64"]})
    assert r.status_code == 200, r.text
    return rid, r.json()["case_id"], xyz, meera


def test_s01_live_returned_rtgs_refund(api):
    rid, case, xyz, meera = _release_online(api)
    ravi = api().login(RAVI, OFF)
    assert ravi.post(f"/api/payments/{case}/initiate").json()["state"] == "INITIATED"
    assert ravi.post(f"/api/sim/payments/{case}/debit").json()["status"] == "ACCEPTED"
    p = xyz.get(f"/api/payments/{case}").json()
    assert p["state"] == "DEBITED" and "NOT yet complete" in p["status_text"] and "Completed" not in p["status_text"]
    assert p["liability"]["in_transit"] == p["amount_paise"]
    assert xyz.get(f"/api/release-requests/{rid}").json()["stage"] == "APPROVED"    # debit + UTR is not completion
    # the beneficiary bank rejects the credit
    assert ravi.post(f"/api/sim/payments/{case}/return", json={"reason_code": "BENEFICIARY_BANK_REJECT"}).json()["status"] == "ACCEPTED"
    p = xyz.get(f"/api/payments/{case}").json()
    assert p["state"] == "REISSUE_REQUIRED" and "AICTE still owes you" in p["status_text"]
    assert p["liability"]["outstanding_liability"] == p["amount_paise"] and p["liability"]["in_transit"] == 0
    assert p["attempts"][0]["status"] == "RETURNED"
    # re-issue to the same verified account, then positive credit confirmation
    assert ravi.post(f"/api/payments/{case}/reissue").json()["state"] == "INITIATED"
    ravi.post(f"/api/sim/payments/{case}/debit")
    assert ravi.post(f"/api/sim/payments/{case}/confirm", json={}).json()["status"] == "ACCEPTED"
    p = xyz.get(f"/api/payments/{case}").json()
    assert p["state"] == "SETTLED" and p["status_text"].startswith("Completed") and len(p["attempts"]) == 2
    assert p["liability"]["outstanding_liability"] == 0
    assert xyz.get(f"/api/release-requests/{rid}").json()["stage"] == "COMPLETED"   # only now, after positive confirmation


def test_settlement_needs_matching_confirmation(api):
    rid, case, xyz, meera = _release_online(api)
    ravi = api().login(RAVI, OFF)
    ravi.post(f"/api/payments/{case}/initiate")
    ravi.post(f"/api/sim/payments/{case}/debit")
    wrong_amt = ravi.post(f"/api/sim/payments/{case}/confirm", json={"amount_paise": 1}).json()
    wrong_acct = ravi.post(f"/api/sim/payments/{case}/confirm", json={"beneficiary_account": "SOMEONE-ELSE"}).json()
    assert wrong_amt["status"] == wrong_acct["status"] == "REJECTED"
    assert xyz.get(f"/api/payments/{case}").json()["state"] == "DEBITED"


def test_return_after_settlement_flagged(api):
    a = api().login(MEERA, OFF)
    out = a.post("/api/sim/payments/RF-SEED-DEF/return", json={"reason_code": "ACCOUNT_CLOSED"}).json()
    assert out["status"] == "ACCEPTED"
    p = a.get("/api/payments/RF-SEED-DEF").json()
    assert p["state"] == "REISSUE_REQUIRED" and p["attempts"][-1]["returned_after_settlement"] is True
    assert any(h["state"] == "RETURNED_AFTER_SETTLEMENT" for h in p["history"])
    # account-related reason: payee must be re-verified (Affidavit-9) before re-issue
    assert p["payee_verified"] is False
    ravi = api().login(RAVI, OFF)
    assert ravi.post("/api/payments/RF-SEED-DEF/reissue").status_code == 409


def test_unique_utr_per_debit(api):
    rid, case, xyz, meera = _release_online(api)
    ravi = api().login(RAVI, OFF)
    ravi.post(f"/api/payments/{case}/initiate")
    used = LEDGER.kernel().refunds["RF-SEED-DEF"]["attempts"][0]["utr"]
    out = _inject(ravi, bank="SBI", kind="debit_advice", payload={"refund_id": case, "utr": used, "amount": LEDGER.kernel().refunds[case]["amount"]})
    assert out["status"] == "REJECTED" and "UTR" in out["reason"]


def test_debit_and_lookup_only_from_finance_bank(api):
    rid, case, xyz, meera = _release_online(api)
    ravi = api().login(RAVI, OFF)
    ravi.post(f"/api/payments/{case}/initiate")
    out = _inject(ravi, bank="HDFC", kind="debit_advice", payload={"refund_id": case, "utr": "HDFCX1", "amount": LEDGER.kernel().refunds[case]["amount"]})
    assert out["status"] == "REJECTED" and "Finance" in out["reason"]


# ------------------------------------------------------------------ maker-checker and gate
def test_maker_checker_scrutiny_officer_cannot_approve(api):
    xyz = api().login(XYZ, INS)
    rid = xyz.post("/api/release-requests", json={"obligation_id": "ONL-XYZ-UG", "reason": "Programme closure approved"}).json()["id"]
    kiran = api().login(KIRAN, OFF)
    kiran.post(f"/api/release-requests/{rid}/scrutiny", json={"entitlement_basis": "Closure approved"})
    gate = kiran.get(f"/api/release-requests/{rid}/gate").json()
    assert not gate["allowed"] and "M_APPROVER_ROLE" in gate["blocked_by"]
    sig = kiran.dsc(KIRAN, gate["approval_message"])
    r = kiran.post(f"/api/release-requests/{rid}/approve", json={"certificate_pem": sig["certificate_pem"], "signature_b64": sig["signature_b64"]})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "MakerChecker"


def test_approver_cannot_initiate_payment(api):
    rid, case, xyz, meera = _release_online(api)
    assert meera.post(f"/api/payments/{case}/initiate").status_code == 403


def test_mandatory_override_refused_logged_and_conflicts_officer(api):
    xyz = api().login(XYZ, INS)
    rid = xyz.post("/api/release-requests", json={"obligation_id": "ONL-XYZ-UG", "reason": "Programme closure approved"}).json()["id"]
    api().login(KIRAN, OFF).post(f"/api/release-requests/{rid}/scrutiny", json={"entitlement_basis": "Closure approved"})
    meera = api().login(MEERA, OFF)
    r = meera.post(f"/api/release-requests/{rid}/override", json={"code": "M_PAYEE_VERIFIED", "reason": "please just pay"})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "MandatoryOverride"
    events = meera.get("/api/audit-trail?q=override_refused").json()["items"]
    assert events and events[0]["actor"] == "deputy_director:meera"
    gate = meera.get(f"/api/release-requests/{rid}/gate").json()
    assert "M_CONFLICT_OF_INTEREST" in gate["blocked_by"]          # the officer is now conflicted on this case


def test_dsc_approval_bound_to_gate(api):
    xyz = api().login(XYZ, INS)
    rid = xyz.post("/api/release-requests", json={"obligation_id": "ONL-XYZ-UG", "reason": "Programme closure approved"}).json()["id"]
    api().login(KIRAN, OFF).post(f"/api/release-requests/{rid}/scrutiny", json={"entitlement_basis": "Closure approved"})
    meera = api().login(MEERA, OFF)
    sig = meera.dsc(MEERA, f"TL-APPROVE:{rid}:something-else")
    r = meera.post(f"/api/release-requests/{rid}/approve", json={"certificate_pem": sig["certificate_pem"], "signature_b64": sig["signature_b64"]})
    assert r.status_code == 401


def test_fdr_release_noc_then_lien_discharge(api):
    abc = api().login("1-12345678", INS)
    rid = abc.post("/api/release-requests", json={"fdr_id": "FDR202600125", "reason": "Replacement with higher-value FDR"}).json()["id"]
    api().login(KIRAN, OFF).post(f"/api/release-requests/{rid}/scrutiny", json={"entitlement_basis": "Replacement approved"})
    meera = api().login(MEERA, OFF)
    gate = meera.get(f"/api/release-requests/{rid}/gate").json()
    assert gate["allowed"], gate["blocked_by"]
    sig = meera.dsc(MEERA, gate["approval_message"])
    r = meera.post(f"/api/release-requests/{rid}/approve", json={"certificate_pem": sig["certificate_pem"], "signature_b64": sig["signature_b64"]})
    assert r.status_code == 200 and r.json()["case_id"].startswith("NOC-")
    assert abc.get("/api/fdrs/FDR202600125").json()["fdr"]["status"] == "verified"   # NOC alone is not completion
    assert meera.post(f"/api/release-requests/{rid}/lien-discharge").json()["status"] == "ACCEPTED"
    assert abc.get("/api/fdrs/FDR202600125").json()["fdr"]["status"] == "released"


# ------------------------------------------------------------------ holds
def test_holds_scoped_and_role_limited(api):
    meera = api().login(MEERA, OFF)
    assert meera.post("/api/holds", json={"instruments": ["INS-FDR202600125"], "basis": "complaint"}).status_code == 403
    anil = api().login(ANIL, OFF)
    assert anil.post("/api/holds", json={"basis": "whole institution"}).status_code == 422
    h = anil.post("/api/holds", json={"instruments": ["INS-FDR202600125"], "basis": "Complaint under review (CMP/2026/14)"})
    assert h.status_code == 200, h.text
    aud = api().login(AUDITOR, AUD)
    assert aud.post("/api/holds", json={"credits": ["CR-UTR-GHI-2016-0909"], "basis": "Internal audit query IA/77"}).status_code == 200
    # the hold blocks FDR release through the gate
    abc = api().login("1-12345678", INS)
    rid = abc.post("/api/release-requests", json={"fdr_id": "FDR202600125", "reason": "Replacement with higher-value FDR"}).json()["id"]
    api().login(KIRAN, OFF).post(f"/api/release-requests/{rid}/scrutiny", json={"entitlement_basis": "Replacement approved"})
    assert "M_NO_HOLD" in meera.get(f"/api/release-requests/{rid}/gate").json()["blocked_by"]


def test_hold_escalates_after_30_days(api, db_path):
    from app.db import SessionLocal
    anil = api().login(ANIL, OFF)
    hid = anil.post("/api/holds", json={"instruments": ["INS-FDR202600125"], "basis": "Complaint under review"}).json()["hold_id"]
    later = (datetime.now() + timedelta(days=31)).isoformat(timespec="seconds")
    with SessionLocal() as db:
        LEDGER.run(db, lambda k: k.tick(later))
    notes = [n for n in LEDGER.kernel().outbox if n["kind"] == "hold_review_due" and n["ref"] == hid]
    assert notes and notes[0]["to"] == "competent_authority"
