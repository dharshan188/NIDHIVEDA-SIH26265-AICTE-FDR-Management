"""Tests added after the first mutation run showed four controls were not pinned by any test."""
import pytest

from trustledger.crypto import TestBankSigner
from trustledger.kernel import GateBlocked, lakh
from conftest import World


def test_hold_on_proven_allocation_blocks_only_that_obligation(world):
    world.ready_online("O1")
    world.ready_online("O2", amount=lakh(10))
    k = world.k
    assert k.evaluate_release("O1", "2026-02-01T10:00", "deputy_director:meera").allowed
    k.place_hold("H1", {"allocations": ["AL-O1"]}, "register shows this credit twice", "2026-02-01T10:01", "finance_reconciliation_officer:anil")
    d = k.evaluate_release("O1", "2026-02-01T10:02", "deputy_director:meera")
    assert "M_ATTRIBUTION" in d.blocked_by and d.releasable == 0
    assert k.evaluate_release("O2", "2026-02-01T10:02", "deputy_director:meera").allowed
    k.release_hold("H1", "2026-02-02T10:00", "director:sunil", "duplicate was a typo")
    assert k.evaluate_release("O1", "2026-02-02T10:01", "deputy_director:meera").allowed


def test_fdr_hold_blocks_noc():
    from test_gates import fdr_world
    w = fdr_world()
    iid = w.k.current_instrument("OF")["instrument_id"]
    w.k.place_hold("HF", {"instruments": [iid]}, "court order", "2026-09-02T09:00", "internal_audit:priya")
    assert "M_NO_HOLD" in w.k.evaluate_release("OF", "2026-09-02T10:00", "deputy_director:meera").blocked_by


def test_recent_evidence_from_before_maturity_is_not_enough():
    """62-day-old confirmation passes the age rule, but the FDR matured after it: bank may have renewed or paid it."""
    w = World()
    k = w.k
    k.register_institution("C", "Gamma", "2026-01-01T00:00")
    k.create_obligation("OF", "C", "x", lakh(15), "FDR", "2026-01-01T00:00")
    k.register_instrument("IF", "OF", "FD-7", "SBI", lakh(15), "2021-08-15", "2026-08-15", "2026-01-01T00:01", "institution:C")
    w.ev("instrument_confirmation", {"instrument_no": "FD-7", "amount": lakh(15), "maturity_date": "2026-08-15", "status": "ACTIVE",
                                     "lien_holder": "AICTE", "as_of": "2026-07-01"}, "2026-07-01T10:00")
    k.record_entitlement("OF", "closure", "2026-08-20T10:00", "section_officer:kiran")
    k.record_affidavit("OF", "AFFIDAVIT-6", True, "2026-08-20T10:00", "section_officer:kiran")
    d = k.evaluate_release("OF", "2026-09-01T10:00", "deputy_director:meera")
    assert "M_CURRENT_INSTRUMENT" in d.blocked_by
    assert "matured after the latest confirmation" in next(c.detail for c in d.checks if c.code == "M_CURRENT_INSTRUMENT")


def test_account_closed_return_forces_payee_reverification(world):
    world.ready_online()
    k = world.k
    k.authorise_release("R", "O1", "2026-02-01T10:00", "deputy_director:meera")
    k.initiate_payment("R", "2026-02-01T11:00", "finance_officer:ravi")
    world.ev("debit_advice", {"refund_id": "R", "utr": "P1", "amount": lakh(35)}, "2026-02-01T11:05")
    world.ev("return_advice", {"original_utr": "P1", "return_utr": "RT1", "amount": lakh(35), "reason_code": "ACCOUNT_CLOSED", "returned_at": "x"}, "2026-02-01T11:50")
    with pytest.raises(GateBlocked):
        k.initiate_payment("R", "2026-02-02T10:00", "finance_officer:ravi")


def test_non_account_return_allows_reissue_to_same_account(world):
    world.ready_online()
    k = world.k
    k.authorise_release("R", "O1", "2026-02-01T10:00", "deputy_director:meera")
    k.initiate_payment("R", "2026-02-01T11:00", "finance_officer:ravi")
    world.ev("debit_advice", {"refund_id": "R", "utr": "P1", "amount": lakh(35)}, "2026-02-01T11:05")
    world.ev("return_advice", {"original_utr": "P1", "return_utr": "RT1", "amount": lakh(35), "reason_code": "BENEFICIARY_BANK_REJECT", "returned_at": "x"}, "2026-02-01T11:50")
    k.initiate_payment("R", "2026-02-02T10:00", "finance_officer:ravi")
    assert k.refunds["R"]["state"] == "INITIATED"


def test_compromised_name_lookup_key_stops_payment():
    """Credit evidence is fine (K1); only the payee name look-up came through K2, which is later compromised."""
    w = World()
    k = w.k
    k2 = TestBankSigner("SBI", "SBI-K2")
    k.register_signer("SBI-K2", "SBI", k2.public_key_b64, "2000-01-01", "2026-01-01T00:00")
    k.create_obligation("O1", "A", "UG", lakh(5), "ONLINE", "2026-01-01T10:00", reference="R1")
    k.allocate("X", w.credit("U1", lakh(5), "2026-01-01T10:00", narrative="R1"), "O1", lakh(5), "machine_reference", "2026-01-01T10:01", "system:auto")
    k.record_entitlement("O1", "closure", "2026-01-01T10:02", "section_officer:kiran")
    k.record_affidavit("O1", "AFFIDAVIT-6", True, "2026-01-01T10:02", "section_officer:kiran")
    k.register_payee("A", "ACC-A", "IFSC1", "Alpha Institute", "2026-01-01T10:03", "institution:A")
    w.ev("name_lookup", {"account": "ACC-A", "ifsc": "IFSC1", "name_at_bank": "Alpha Institute"}, "2026-01-02T10:00", signer=k2)
    k.authorise_release("R", "O1", "2026-01-03T10:00", "deputy_director:meera")
    k.compromise_signer("SBI-K2", "2026-01-02T00:00", "2026-01-04T10:00", "leak")
    assert "M_PAYEE_VERIFIED" in k.evaluate_release("O1", "2026-01-04T11:00", "director:sunil").blocked_by
    with pytest.raises(GateBlocked):
        k.initiate_payment("R", "2026-01-04T11:00", "finance_officer:ravi")
