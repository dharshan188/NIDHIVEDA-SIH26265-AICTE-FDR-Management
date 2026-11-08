"""The five faults reproduced by the independent V7 review (its script, turned into assertions that the fault is now refused)."""
import pytest

from trustledger.crypto import TestBankSigner
from trustledger.kernel import InvalidEvidence, StateError, lakh
from conftest import World


def pnb_fdr():
    w = World()
    k = w.k
    pnb = TestBankSigner("PNB", "PNB-K1")
    k.register_signer("PNB-K1", "PNB", pnb.public_key_b64, "2000-01-01", "2026-01-01T08:00")
    k.register_institution("C", "Gamma Institute", "2026-01-01T09:00")
    k.create_obligation("OF", "C", "UG", lakh(15), "FDR", "2026-01-01T09:10")
    k.register_instrument("FI", "OF", "PNB-FD-888", "PNB", lakh(15), "2020-01-01", "2026-01-02", "2026-01-01T09:20", "institution:C")
    k.record_entitlement("OF", "Matured", "2026-01-03T09:00", "section_officer:kiran")
    k.record_affidavit("OF", "AFFIDAVIT-6", True, "2026-01-03T09:01", "section_officer:kiran")
    return w, pnb


def test_V7_1_other_bank_cannot_confirm_fdr():
    w, pnb = pnb_fdr()
    conf = dict(instrument_no="PNB-FD-888", amount=lakh(15), maturity_date="2026-01-02", status="ACTIVE", lien_holder="AICTE", as_of="2026-01-03")
    with pytest.raises(InvalidEvidence):
        w.ev("instrument_confirmation", conf, "2026-01-03T10:00")          # SBI key
    assert not w.k.evaluate_release("OF", "2026-01-04T11:00", "deputy_director:meera").allowed
    w.ev("instrument_confirmation", conf, "2026-01-03T10:01", signer=pnb)  # issuing bank: accepted
    assert w.k.evaluate_release("OF", "2026-01-04T11:00", "deputy_director:meera").allowed


def test_V7_2_other_bank_cannot_discharge_lien():
    w, pnb = pnb_fdr()
    w.ev("instrument_confirmation", dict(instrument_no="PNB-FD-888", amount=lakh(15), maturity_date="2026-01-02", status="ACTIVE", lien_holder="AICTE", as_of="2026-01-03"), "2026-01-03T10:00", signer=pnb)
    w.k.authorise_release("NOC-1", "OF", "2026-01-04T11:01", "deputy_director:meera")
    with pytest.raises(InvalidEvidence):
        w.ev("lien_discharge", {"instrument_no": "PNB-FD-888", "discharged_at": "2026-01-04"}, "2026-01-04T11:02")
    assert w.k.nocs["NOC-1"]["state"] == "NOC_ISSUED"


def test_V7_3_payment_utr_unique_across_refunds():
    w = World()
    k = w.k
    w.ready_online("O1", "A", at="2026-01-01T10:00")
    w.ready_online("O2", "B", at="2026-01-02T10:00")
    k.authorise_release("R1", "O1", "2026-02-01T10:00", "deputy_director:meera")
    k.authorise_release("R2", "O2", "2026-02-01T10:01", "deputy_director:meera")
    k.initiate_payment("R1", "2026-02-01T11:00", "finance_officer:ravi")
    k.initiate_payment("R2", "2026-02-01T11:01", "finance_officer:ravi")
    w.ev("debit_advice", {"refund_id": "R1", "utr": "DUP-UTR", "amount": lakh(35)}, "2026-02-01T11:05")
    with pytest.raises(InvalidEvidence):
        w.ev("debit_advice", {"refund_id": "R2", "utr": "DUP-UTR", "amount": lakh(35)}, "2026-02-01T11:06")
    assert k.attempt_by_utr["DUP-UTR"][0] == "R1"


def test_V7_4_case_id_unique():
    w = World()
    k = w.k
    w.ready_online("O1", "A", at="2026-01-01T10:00")
    w.ready_online("O2", "B", at="2026-01-02T10:00")
    k.authorise_release("R-SAME", "O1", "2026-02-01T10:00", "deputy_director:meera")
    with pytest.raises(StateError):
        k.authorise_release("R-SAME", "O2", "2026-02-01T10:01", "deputy_director:meera")
    assert k.refunds["R-SAME"]["obligation_id"] == "O1"


def test_V7_5_name_lookup_only_from_finance_bank():
    w = World()
    k = w.k
    w.ready_online("O1", "A", at="2026-01-01T10:00")
    other = TestBankSigner("HDFC", "HDFC-K1")
    k.register_signer("HDFC-K1", "HDFC", other.public_key_b64, "2000-01-01", "2026-01-01T10:01")
    before = k.payees["A"]["lookup_evidence"]
    with pytest.raises(InvalidEvidence):
        w.ev("name_lookup", {"account": "ACC-A", "ifsc": "IFSC0001", "name_at_bank": "Alpha Institute"}, "2026-01-01T10:02", signer=other)
    assert k.payees["A"]["lookup_evidence"] == before
