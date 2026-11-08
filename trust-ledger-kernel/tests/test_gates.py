import copy

import pytest

from trustledger.kernel import GateBlocked, StateError, lakh, load_policy
from conftest import World


def fdr_world(policy=None, remark="Auto-renewed; lien continued", as_of="2026-09-01"):
    w = World(policy=policy)
    k = w.k
    k.register_institution("C", "Gamma", "2014-01-01T00:00")
    k.create_obligation("OF", "C", "Planning", lakh(15), "FDR", "2014-01-02T00:00")
    k.register_instrument("IF", "OF", "FD-1", "SBI", lakh(15), "2014-02-15", "2019-02-15", "2014-02-16T00:00", "institution:C")
    w.ev("instrument_confirmation", {"instrument_no": "FD-2", "supersedes": "FD-1", "change_kind": "auto_renewal", "changed_on": "2019-02-15",
                                     "amount": lakh(15), "maturity_date": "2029-02-15", "status": "ACTIVE", "lien_holder": "AICTE",
                                     "as_of": as_of, "remark": remark}, as_of + "T10:00")
    k.record_entitlement("OF", "closure", "2026-09-01T11:00", "section_officer:kiran")
    k.record_affidavit("OF", "AFFIDAVIT-6", True, "2026-09-01T11:00", "section_officer:kiran")
    k.confirm_rule_pack("APH-2018-19", "2026-09-01T11:00", "legal_cell:asha", "LC/1")
    return w


def test_auto_renewal_without_bank_remark_blocks():
    w = fdr_world(remark=None)
    d = w.k.evaluate_release("OF", "2026-09-02T10:00", "deputy_director:meera")
    assert "M_RENEWAL_RULES" in d.blocked_by


def test_evidence_age_boundary_90_vs_91_days():
    w = fdr_world(as_of="2026-06-04")
    assert w.k.evaluate_release("OF", "2026-09-02T10:00", "deputy_director:meera").allowed      # 90 days
    assert "M_CURRENT_INSTRUMENT" in w.k.evaluate_release("OF", "2026-09-03T10:00", "deputy_director:meera").blocked_by  # 91


def test_evidence_age_is_policy_data_not_code():
    pol = copy.deepcopy(load_policy())
    pol["release"]["fdr_current_instrument_max_evidence_age_days"] = 30
    w = fdr_world(policy=pol, as_of="2026-07-20")
    assert "M_CURRENT_INSTRUMENT" in w.k.evaluate_release("OF", "2026-09-02T10:00", "deputy_director:meera").blocked_by


def test_noc_names_current_instrument_number():
    w = fdr_world()
    w.k.authorise_release("N1", "OF", "2026-09-02T10:00", "deputy_director:meera")
    assert w.k.nocs["N1"]["instrument_no"] == "FD-2"


def test_partial_release_can_be_switched_off_by_policy():
    pol = copy.deepcopy(load_policy())
    pol["release"]["allow_partial_release_of_undisputed_amount"] = False
    w = World(policy=pol)
    w.ready_online(amount=lakh(20))
    k = w.k
    k.create_obligation("O2", "A", "PG", lakh(30), "ONLINE", "2026-01-02T10:00", reference="REF-O2")
    k.allocate("X1", w.credit("U-a", lakh(20), "2026-01-02T10:00", narrative="REF-O2"), "O2", lakh(20), "machine_reference", "2026-01-02T10:01", "system:auto")
    k.allocate("X2", w.credit("U-b", lakh(10), "2026-01-02T10:02"), "O2", lakh(10), "institution_declaration", "2026-01-02T10:03", "finance_reconciliation_officer:a")
    k.record_entitlement("O2", "closure", "2026-01-03T10:00", "section_officer:kiran")
    k.record_affidavit("O2", "AFFIDAVIT-6", True, "2026-01-03T10:00", "section_officer:kiran")
    with pytest.raises(GateBlocked):
        k.authorise_release("R2", "O2", "2026-01-04T10:00", "deputy_director:meera")


def test_payee_name_mismatch_blocks_release():
    w = World()
    k = w.k
    k.create_obligation("O1", "A", "UG", lakh(5), "ONLINE", "2026-01-01T10:00", reference="R1")
    k.allocate("X", w.credit("U1", lakh(5), "2026-01-01T10:00", narrative="R1"), "O1", lakh(5), "machine_reference", "2026-01-01T10:01", "system:auto")
    k.record_entitlement("O1", "closure", "2026-01-01T10:02", "section_officer:kiran")
    k.record_affidavit("O1", "AFFIDAVIT-6", True, "2026-01-01T10:02", "section_officer:kiran")
    k.register_payee("A", "ACC-A", "IFSC1", "Alpha Institute", "2026-01-01T10:03", "institution:A")
    w.ev("name_lookup", {"account": "ACC-A", "ifsc": "IFSC1", "name_at_bank": "Alpha Traders Pvt Ltd"}, "2026-01-01T10:04")
    d = k.evaluate_release("O1", "2026-01-02T10:00", "deputy_director:meera")
    assert d.blocked_by == ["M_PAYEE_VERIFIED"]
    assert any(n["kind"] == "payee_name_mismatch" for n in k.outbox)


def test_payee_change_requires_affidavit_9_and_fee(world):
    world.ready_online()
    with pytest.raises(StateError):
        world.k.register_payee("A", "ACC-X", "IFSC9", "Alpha Institute", "2026-02-01T10:00", "institution:A")
    with pytest.raises(StateError):
        world.k.register_payee("A", "ACC-X", "IFSC9", "Alpha Institute", "2026-02-01T10:00", "institution:A", change_basis={"affidavit": "AFFIDAVIT-9"})


def test_release_rules_gap_blocks_instead_of_guessing():
    w = World()
    w.ready_online(at="2021-06-01T10:00")
    d = w.k.evaluate_release("O1", "2021-06-02T10:00", "deputy_director:meera")
    assert "M_RULES" in d.blocked_by


def test_time_cannot_run_backwards(world):
    world.ready_online(at="2026-01-05T10:00")
    with pytest.raises(StateError):
        world.k.record_entitlement("O1", "x", "2026-01-04T10:00", "section_officer:kiran")
