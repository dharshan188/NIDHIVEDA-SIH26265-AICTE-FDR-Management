import pytest
pytest.importorskip("hypothesis")
"""Property-based tests: Hypothesis generates thousands of random operation sequences
and checks that the financial invariants hold after every single step."""
from datetime import datetime, timedelta

from hypothesis import event, given, settings, strategies as st

from trustledger.kernel import DomainError, Kernel, lakh
from conftest import World

T0 = datetime(2026, 1, 1, 9, 0)


def ts(i):
    return (T0 + timedelta(minutes=7 * i)).isoformat(timespec="minutes")


def identity_holds(k):
    unalloc = sum(k.remaining_on_credit(c) for c, v in k.credits.items() if v["kind"] == "deposit")
    out = sum(k.liability_register(o)["outstanding_liability"] for o in k.obligations)
    transit = sum(k.liability_register(o)["in_transit"] for o in k.obligations)
    return k.book_balance() == out + unalloc - transit


alloc_op = st.tuples(st.integers(0, 2), st.integers(0, 3), st.integers(1, 60))


@settings(max_examples=300, deadline=None)
@given(credit_amts=st.lists(st.integers(1, 60), min_size=3, max_size=3),
       obl_amts=st.lists(st.integers(1, 60), min_size=4, max_size=4),
       ops=st.lists(alloc_op, max_size=25))
def test_allocation_invariants_many_to_many(credit_amts, obl_amts, ops):
    w = World()
    k = w.k
    insts = ["A", "A", "B", "B"]
    for j, amt in enumerate(obl_amts):
        k.create_obligation(f"O{j}", insts[j], "p", lakh(amt), "ONLINE", ts(0))
    for i, amt in enumerate(credit_amts):
        w.credit(f"U{i}", lakh(amt), ts(1))
    for n, (ci, oj, amt) in enumerate(ops):
        try:
            k.allocate(f"X{n}", f"CR-U{ci}", f"O{oj}", lakh(amt), "institution_declaration", ts(2 + n), "finance_reconciliation_officer:t")
        except DomainError as e:
            assert e.code == "OverAllocation"
        for i, amt in enumerate(credit_amts):
            assert 0 <= k.remaining_on_credit(f"CR-U{i}") <= lakh(amt)          # allocated <= received
        for j, amt in enumerate(obl_amts):
            assert 0 <= k.allocated_to(f"O{j}") <= lakh(amt)                   # allocated <= required
        assert identity_holds(k)
    assert Kernel.replay(k.store, k.policy, k._packs).snapshot() == k.snapshot()


ACTIONS = ["pay", "pay", "initiate", "debit", "confirm", "confirm", "return_tech", "return_closed", "tick", "reverify"]


@settings(max_examples=1500, deadline=None)
@given(seq=st.lists(st.sampled_from(ACTIONS), max_size=30))
def test_payment_lifecycle_never_reports_false_completion(seq):
    w = World()
    k = w.k
    w.ready_online(at=ts(0))
    k.authorise_release("R", "O1", ts(1), "deputy_director:meera")
    utr_n = 0
    for i, a in enumerate(seq, start=2):
        t = ts(i)
        r = k.refunds["R"]
        last = r["attempts"][-1] if r["attempts"] else None
        try:
            if a == "pay":   # macro: initiate then debit (the common path)
                k.initiate_payment("R", t, "finance_officer:ravi")
                utr_n += 1
                w.ev("debit_advice", {"refund_id": "R", "utr": f"P{utr_n}", "amount": r["amount"]}, ts(i) + ":30")
            elif a == "initiate":
                k.initiate_payment("R", t, "finance_officer:ravi")
            elif a == "debit":
                utr_n += 1
                w.ev("debit_advice", {"refund_id": "R", "utr": f"P{utr_n}", "amount": r["amount"]}, t)
            elif a == "confirm" and last:
                w.ev("credit_confirmation", {"utr": last["utr"], "credited_at": t, "amount": last["amount"], "beneficiary_account": last["beneficiary_account"]}, t)
            elif a.startswith("return") and last:
                reason = "ACCOUNT_CLOSED" if a == "return_closed" else "BENEFICIARY_BANK_REJECT"
                w.ev("return_advice", {"original_utr": last["utr"], "return_utr": f"RT{i}", "amount": last["amount"], "reason_code": reason, "returned_at": t}, t)
            elif a == "tick":
                k.tick(t)
            elif a == "reverify":
                k.register_payee("A", f"ACC-NEW{i}", "IFSC0002", "Alpha Institute", t, "institution:A",
                                 change_basis={"affidavit": "AFFIDAVIT-9", "ter_fee_paid": True})
                w.ev("name_lookup", {"account": f"ACC-NEW{i}", "ifsc": "IFSC0002", "name_at_bank": "Alpha Institute"}, t)
        except DomainError:
            pass  # invalid in this state: refused, and refusals of evidence are themselves audited
        r = k.refunds["R"]
        lr = k.liability_register("O1")
        settled_attempts = [x for x in r["attempts"] if x["status"] == "SETTLED"]
        # 1. Completion only with positive credit confirmation evidence
        if r["state"] == "SETTLED":
            assert r["attempts"][-1]["status"] == "SETTLED" and r["attempts"][-1].get("confirm_evidence")
        # 2. Never settled twice; liability discharged only by settled attempts
        assert len(settled_attempts) <= 1
        assert lr["outstanding_liability"] == lakh(35) - sum(x["amount"] for x in settled_attempts)
        # 3. Portal never says Completed unless settled
        assert ("Completed" in k.refund_status_text("R")) == (r["state"] == "SETTLED")
        # 4. Cash identity holds through debits and returns
        assert identity_holds(k)
        # 5. At most one attempt in flight
        assert sum(1 for x in r["attempts"] if x["status"] == "DEBITED") <= 1
    r = k.refunds["R"]
    event(f"final state {r['state']}")
    event(f"attempts={len(r['attempts'])} returned={sum(x['status'] == 'RETURNED' for x in r['attempts'])}")
    if any(x.get("returned_after_settlement") for x in r["attempts"]):
        event("reached: return AFTER settlement")
    assert k.store.verify() == (True, None)
    assert Kernel.replay(k.store, k.policy, k._packs).snapshot() == k.snapshot()
