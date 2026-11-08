"""Regression tests for the seven defects an independent V6 review found in our v5 kernel."""
import pytest

from trustledger.crypto import TestBankSigner
from trustledger.kernel import InvalidEvidence, OverAllocation, StateError, lakh
from conftest import World


def paid(world):
    world.ready_online()
    k = world.k
    k.authorise_release("R", "O1", "2026-02-01T10:00", "deputy_director:meera")
    k.initiate_payment("R", "2026-02-01T11:00", "finance_officer:ravi")
    world.ev("debit_advice", {"refund_id": "R", "utr": "P1", "amount": lakh(35)}, "2026-02-01T11:05")
    other = TestBankSigner("HDFC", "HDFC-K1")
    k.register_signer("HDFC-K1", "HDFC", other.public_key_b64, "2000-01-01", "2026-02-01T11:06")
    return other


def test_T01_other_bank_cannot_settle_or_return(world):
    other = paid(world)
    with pytest.raises(InvalidEvidence):
        world.ev("credit_confirmation", {"utr": "P1", "credited_at": "x"}, "2026-02-01T11:10", signer=other)
    with pytest.raises(InvalidEvidence):
        world.ev("return_advice", {"original_utr": "P1", "return_utr": "Z", "amount": lakh(35), "reason_code": "X", "returned_at": "x"}, "2026-02-01T11:11", signer=other)
    assert world.k.refunds["R"]["state"] == "DEBITED"


def test_T02_other_bank_cannot_assert_remitter(world):
    other = paid(world)
    with pytest.raises(InvalidEvidence):
        world.ev("remitter_details", {"utr": "UTR-O1", "remitter_name": "Beta College", "remitter_account": "ACC-B"}, "2026-02-01T11:12", signer=other)


def test_T03_dispute_award_cannot_overfund_obligation():
    w = World()
    k = w.k
    k.create_obligation("OA", "A", "x", lakh(20), "ONLINE", "2026-01-01T10:00")
    k.create_obligation("OB", "B", "x", lakh(50), "ONLINE", "2026-01-01T10:00")
    c = w.credit("U50", lakh(50), "2026-01-01T10:01")
    k.allocate("AB", c, "OB", lakh(50), "institution_declaration", "2026-01-01T10:02", "finance_reconciliation_officer:a")
    k.allocate("AA", c, "OA", lakh(20), "institution_declaration", "2026-01-01T10:03", "finance_reconciliation_officer:a")  # competing -> dispute
    with pytest.raises(OverAllocation):
        k.resolve_dispute("DSP-" + c, "2026-01-02T10:00", "director:sunil", "order", {"AA": lakh(50), "AB": 0})
    k.resolve_dispute("DSP-" + c, "2026-01-02T10:01", "director:sunil", "order", {"AA": lakh(20), "AB": lakh(30)})
    assert k.remaining_on_credit(c) == 0 and k.allocated_to("OA") == lakh(20)


def test_T04_award_item_must_belong_to_disputed_credit():
    w = World()
    k = w.k
    k.create_obligation("OA", "A", "x", lakh(20), "ONLINE", "2026-01-01T10:00")
    c = w.credit("U1", lakh(20), "2026-01-01T10:01")
    c2 = w.credit("U2", lakh(20), "2026-01-01T10:01")
    k.allocate("X", c2, "OA", lakh(5), "institution_declaration", "2026-01-01T10:02", "finance_reconciliation_officer:a")
    k.open_dispute("D", c, ["A", "B"], "basis", "2026-01-01T10:03", "finance_reconciliation_officer:a")
    with pytest.raises(StateError):
        k.resolve_dispute("D", "2026-01-02T10:00", "director:sunil", "order", {"X": lakh(5)})


def test_T05_evidence_id_reuse(world):
    k = world.k
    env = world.bank.sign("credit_advice", {"utr": "D1", "amount": 1, "value_date": "2026-01-01", "narrative": ""}, "2026-01-01T10:00")
    k.record_bank_evidence("EX", env, "2026-01-01T10:00")
    n = len(k.store)
    k.record_bank_evidence("EX", env, "2026-01-01T10:01")         # identical re-delivery: no-op
    assert len(k.store) == n
    env2 = world.bank.sign("credit_advice", {"utr": "D2", "amount": 9, "value_date": "2026-01-01", "narrative": ""}, "2026-01-01T10:02")
    with pytest.raises(InvalidEvidence):
        k.record_bank_evidence("EX", env2, "2026-01-01T10:02")


def test_T05a_allocation_id_reuse(world):
    world.ready_online()
    c = world.credit("D9", lakh(1), "2026-01-02T10:00")
    with pytest.raises(StateError):
        world.k.allocate("AL-O1", c, "O1", lakh(1), "institution_declaration", "2026-01-02T10:01", "finance_reconciliation_officer:a")


def test_T06_reference_prefix_does_not_match(world):
    k = world.k
    k.create_obligation("O12", "A", "x", lakh(5), "ONLINE", "2026-01-01T10:00", reference="APP-12")
    c = world.credit("D3", lakh(5), "2026-01-01T10:01", narrative="SD APP-1234")
    with pytest.raises(StateError):
        k.allocate("Z", c, "O12", lakh(5), "machine_reference", "2026-01-01T10:02", "system:auto")


def test_T07_invalid_pool_evidence_never_matches():
    w = World()
    k = w.k
    w.ev("pooled_balance", {"balance": 0, "as_of": "2026-01-01"}, "2026-03-01T10:00")
    assert k.certification_report()["aggregate_matches"]
    k.compromise_signer("SBI-K1", "2026-02-01T00:00", "2026-03-02T10:00", "leak")
    assert not k.certification_report()["aggregate_matches"]
