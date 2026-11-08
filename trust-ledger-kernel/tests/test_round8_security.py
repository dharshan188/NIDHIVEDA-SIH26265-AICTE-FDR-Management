"""Independent fifth-round security regression tests for FDR Trust Ledger.
Copy to trust-ledger-kernel/tests/test_round8_security.py and run:
    python -m pytest -v tests/test_round8_security.py
These assertions express REQUIRED safe behavior; they FAIL on the 2026-10-23 uploaded archive.
No real banks or accounts are used. All values and signatures are synthetic.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "tests" else Path.cwd()
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT / "tests"))
from conftest import World
from trustledger.crypto import TestBankSigner
from trustledger.kernel import lakh, DomainError

def probe_wrong_fdr_amount():
    w=World(); k=w.k
    k.create_obligation('O-F','A','UG',lakh(15),'FDR','2026-01-01T10:00')
    k.register_instrument('INS','O-F','FDR-15','SBI',lakh(15),'2020-01-01','2026-01-01','2026-01-01T10:02','institution:A')
    k.record_entitlement('O-F','closure','2026-01-02T10:00','section_officer:kiran')
    k.record_affidavit('O-F','AFFIDAVIT-6',True,'2026-01-02T10:01','section_officer:kiran')
    w.ev('instrument_confirmation',{'instrument_no':'FDR-15','amount':lakh(1),'maturity_date':'2026-01-01','status':'ACTIVE','lien_holder':'AICTE','as_of':'2026-01-02'},'2026-01-02T10:02')
    d=k.evaluate_release('O-F','2026-01-02T10:03','deputy_director:meera')
    return {'recorded_lakh':15,'bank_confirmed_lakh':1,'allowed':d.allowed,'blocked':d.blocked_by}

def probe_duplicate_obligation():
    w=World(); k=w.k
    w.ready_online('O1','A')
    bef=(k.obligations['O1']['inst_id'],k.allocated_to('O1'))
    k.create_obligation('O1','B','UG',lakh(35),'ONLINE','2026-01-01T10:01',reference='REF-O1')
    after=(k.obligations['O1']['inst_id'],k.allocated_to('O1'))
    k.register_payee('B','ACC-B','IFSC0001','Beta College','2026-01-01T10:02','institution:B')
    w.ev('name_lookup',{'account':'ACC-B','ifsc':'IFSC0001','name_at_bank':'Beta College'},'2026-01-01T10:03')
    d=k.evaluate_release('O1','2026-02-01T09:00','deputy_director:meera')
    return {'before':bef,'after':after,'release_allowed_for_B':d.allowed,'funding':k.funding_breakdown('O1')}

def probe_duplicate_instrument():
    w=World();k=w.k
    pnb=TestBankSigner('PNB','PNB-K1');k.register_signer('PNB-K1','PNB',pnb.public_key_b64,'2000-01-01','2026-01-01T08:00')
    k.create_obligation('OF','A','UG',lakh(15),'FDR','2026-01-01T09:00')
    k.register_instrument('INS','OF','PNB-FD-111','PNB',lakh(15),'2020-01-01','2026-01-02','2026-01-01T09:30','institution:A')
    k.register_instrument('INS','OF','SBI-FD-222','SBI',lakh(15),'2020-01-01','2026-01-02','2026-01-01T09:31','institution:A')
    w.ev('instrument_confirmation',{'instrument_no':'PNB-FD-111','amount':lakh(15),'maturity_date':'2026-01-02','status':'ACTIVE','lien_holder':'AICTE','as_of':'2026-01-03'},'2026-01-03T10:00')
    return {'prior_number':'PNB-FD-111','indexed_bank':k.instruments[k.instr_by_no['PNB-FD-111']]['bank'],'sbi_signed_pnb_number_accepted':True}

def probe_duplicate_noc():
    w=World();k=w.k
    k.create_obligation('OF','A','UG',lakh(15),'FDR','2026-01-01T09:00')
    k.register_instrument('INS','OF','SBI-FD-123','SBI',lakh(15),'2020-01-01','2026-01-02','2026-01-01T09:30','institution:A')
    k.record_entitlement('OF','closure','2026-01-03T09:30','section_officer:kiran')
    k.record_affidavit('OF','AFFIDAVIT-6',True,'2026-01-03T09:31','section_officer:kiran')
    w.ev('instrument_confirmation',{'instrument_no':'SBI-FD-123','amount':lakh(15),'maturity_date':'2026-01-02','status':'ACTIVE','lien_holder':'AICTE','as_of':'2026-01-03'},'2026-01-03T10:00')
    a=k.authorise_release('NOC-A','OF','2026-01-03T11:00','deputy_director:meera')
    b=k.authorise_release('NOC-B','OF','2026-01-03T11:01','director:someone_else')
    return {'noc_count':len(k.nocs),'nocs':[(n['noc_id'],n['instrument_no']) for n in k.nocs.values()]}

def probe_wrong_beneficiary_confirmation():
    w=World();k=w.k;w.ready_online()
    k.authorise_release('R1','O1','2026-02-01T10:00','deputy_director:meera')
    k.initiate_payment('R1','2026-02-01T10:01','finance_officer:ravi')
    w.ev('debit_advice',{'refund_id':'R1','utr':'BANK-UTR-111','amount':lakh(35)},'2026-02-01T10:02')
    w.ev('credit_confirmation',{'utr':'BANK-UTR-111','credited_at':'2026-02-01T10:03','amount':1,'beneficiary_account':'UNRELATED-BENEFICIARY'},'2026-02-01T10:03')
    return {'signed_payload_amount':1,'recipient':'UNRELATED-BENEFICIARY','recorded_refund_amount':lakh(35),'state':k.refunds['R1']['state']}

def test_t16_fdr_amount_mismatch_must_block_release():
    try:
        result = probe_wrong_fdr_amount()
    except DomainError:
        return  # rejecting the wrong bank-confirmed principal is safe
    assert result["allowed"] is False, result


def test_t17_duplicate_obligation_id_must_not_change_ownership():
    try:
        result = probe_duplicate_obligation()
    except DomainError:
        return
    assert result["after"][0] == "A" and not result["release_allowed_for_B"], result


def test_t18_duplicate_instrument_id_must_not_rebind_bank_authority():
    try:
        result = probe_duplicate_instrument()
    except DomainError:
        return
    assert result["indexed_bank"] == "PNB" and result["sbi_signed_pnb_number_accepted"] is False, result


def test_t19_second_noc_for_same_fdr_must_be_refused():
    try:
        result = probe_duplicate_noc()
    except DomainError:
        return
    assert result["noc_count"] == 1, result


def test_t20_mismatched_bank_credit_ack_must_not_settle_full_refund():
    try:
        result = probe_wrong_beneficiary_confirmation()
    except DomainError:
        return
    assert result["state"] != "SETTLED", result


# ---- our additions: the negative tests the audit's acceptance gate asked for ----
import pytest
from trustledger.kernel import StateError, InvalidEvidence


def test_duplicate_signer_and_institution_ids_refused():
    w = World()
    with pytest.raises(StateError):
        w.k.register_signer("SBI-K1", "SBI", w.bank.public_key_b64, "2000-01-01", "2026-01-01T00:00")
    with pytest.raises(StateError):
        w.k.register_institution("A", "Other", "2026-01-01T00:00")
    with pytest.raises(StateError):
        w.k.register_institution("Z", "Zed", "2026-01-01T00:00", known_accounts=["ACC-A"])


def test_malformed_fdr_amount_refused():
    w = World(); k = w.k
    k.create_obligation("OF", "A", "UG", lakh(15), "FDR", "2026-01-01T10:00")
    k.register_instrument("I", "OF", "FD-1", "SBI", lakh(15), "2020-01-01", "2030-01-01", "2026-01-01T10:01", "institution:A")
    with pytest.raises(InvalidEvidence):
        w.ev("instrument_confirmation", {"instrument_no": "FD-1", "amount": "15 lakh", "maturity_date": "2030-01-01", "status": "ACTIVE", "lien_holder": "AICTE", "as_of": "2026-01-02"}, "2026-01-02T10:00")


def test_correct_confirmation_still_settles():
    w = World(); k = w.k; w.ready_online()
    k.authorise_release("R1", "O1", "2026-02-01T10:00", "deputy_director:meera")
    k.initiate_payment("R1", "2026-02-01T10:01", "finance_officer:ravi")
    w.ev("debit_advice", {"refund_id": "R1", "utr": "U1", "amount": lakh(35)}, "2026-02-01T10:02")
    w.ev("credit_confirmation", {"utr": "U1", "credited_at": "x", "amount": lakh(35), "beneficiary_account": "ACC-A"}, "2026-02-01T10:03")
    assert k.refunds["R1"]["state"] == "SETTLED"


def test_replay_still_identical_after_refusals():
    from trustledger.kernel import Kernel
    w = World(); k = w.k; w.ready_online()
    for probe in (lambda: k.create_obligation("O1", "B", "UG", lakh(1), "ONLINE", "2026-01-01T10:05"),):
        with pytest.raises(StateError):
            probe()
    assert Kernel.replay(k.store, k.policy, k._packs).snapshot() == k.snapshot()


def _debited():
    w = World(); k = w.k; w.ready_online()
    k.authorise_release("R1", "O1", "2026-02-01T10:00", "deputy_director:meera")
    k.initiate_payment("R1", "2026-02-01T10:01", "finance_officer:ravi")
    w.ev("debit_advice", {"refund_id": "R1", "utr": "U1", "amount": lakh(35)}, "2026-02-01T10:02")
    return w


def test_t20a_wrong_amount_alone_refused():
    w = _debited()
    with pytest.raises(InvalidEvidence):
        w.ev("credit_confirmation", {"utr": "U1", "credited_at": "x", "amount": 1, "beneficiary_account": "ACC-A"}, "2026-02-01T10:03")
    assert w.k.refunds["R1"]["state"] == "DEBITED"


def test_t20b_wrong_beneficiary_alone_refused():
    w = _debited()
    with pytest.raises(InvalidEvidence):
        w.ev("credit_confirmation", {"utr": "U1", "credited_at": "x", "amount": lakh(35), "beneficiary_account": "OTHER"}, "2026-02-01T10:03")
    assert w.k.refunds["R1"]["state"] == "DEBITED"
