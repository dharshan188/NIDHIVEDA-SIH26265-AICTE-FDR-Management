"""Database invariants, rules escalation, legacy import, audit chain, scenarios, dashboard figures."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from app import models as m
from app.db import SessionLocal
from app.ledger import LEDGER, LedgerError
from conftest import ANIL, AUD, AUDITOR, LEGAL, MEERA, OFF
from sequence_clock import SequenceClock, guarded_run

LAKH = 100_000 * 100
_COUNTER = __import__("itertools").count(1)


# ------------------------------------------------------------------ DB-enforced invariants (bypassing the kernel)
def test_db_refuses_over_allocation_of_a_credit(db_path):
    with SessionLocal() as db:
        db.add(m.Obligation(obligation_id="X-O", institution_id="INST0003", programme="t", instrument_class="ONLINE", amount_paise=100 * LAKH))
        db.flush()
        # CR-UTR-LMN-2017-0507 (50 L) is fully allocated 35 + 15 in the seed
        db.add(m.Allocation(alloc_id="X-A", credit_id="CR-UTR-LMN-2017-0507", obligation_id="X-O", amount_paise=1, basis="institution_declaration"))
        with pytest.raises((IntegrityError, OperationalError, ProgrammingError), match="exceed credit"):
            db.flush()


def test_db_refuses_allocation_beyond_required(db_path):
    with SessionLocal() as db:
        db.add(m.BankCredit(credit_id="X-C", utr="X-UTR", amount_paise=100 * LAKH, kind="deposit", bank="SBI", evidence_id="x", value_date="2026-01-01"))
        db.flush()
        db.add(m.Allocation(alloc_id="X-A", credit_id="X-C", obligation_id="ONL-XYZ-UG", amount_paise=1, basis="institution_declaration"))
        with pytest.raises((IntegrityError, OperationalError, ProgrammingError), match="exceed required"):
            db.flush()


def test_db_refuses_allocating_a_returned_payment(db_path):
    with SessionLocal() as db:
        ret = db.scalars(select(m.BankCredit).where(m.BankCredit.kind == "return")).first()
        db.add(m.Allocation(alloc_id="X-A", credit_id=ret.credit_id, obligation_id="ONL-PQR-UG", amount_paise=1, basis="institution_declaration"))
        with pytest.raises((IntegrityError, OperationalError, ProgrammingError), match="returned-payment"):
            db.flush()


def test_db_unique_utr_per_debit_and_fdr_per_bank(db_path):
    with SessionLocal() as db:
        a = db.scalars(select(m.PaymentAttempt)).first()
        db.add(m.PaymentAttempt(refund_id=a.refund_id, attempt_no=99, utr=a.utr, amount_paise=1, status="DEBITED", debited_at="x"))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        f = db.get(m.Fdr, "FDR202600125")
        db.add(m.Instrument(instrument_id="X-I", obligation_id=f.obligation_id, number=f.instrument_no, bank=f.bank, amount_paise=1,
                            maturity_date="2030-01-01", status="ACTIVE", source="x"))
        with pytest.raises(IntegrityError):
            db.flush()


def test_event_store_is_insert_only(db_path):
    with SessionLocal() as db:
        with pytest.raises((IntegrityError, OperationalError, ProgrammingError), match="insert-only"):
            db.execute(text("DELETE FROM kernel_events WHERE seq = 1"))


def _fresh_online(db, n: int, clock):
    """A credit and two obligations owned by a seeded online institution, created through the kernel."""
    at = clock.next()
    from app.bank.deliver import deliver
    from app.bank.simulator import gateway
    env = gateway(db).advice.credit_advice("SBI", f"HYP-{n}", 50 * LAKH, at[:10], "Hyp", "HYP-ACCT", "deposit")
    assert deliver(db, env, evidence_id=f"E-HYP-{n}", at=at)["status"] == "ACCEPTED"
    for j in range(2):
        at = clock.next()
        guarded_run(db, at, lambda k, j=j, at=at: k.create_obligation(f"HYP-{n}-{j}", "INST0003", "t", (20 + 10 * j) * LAKH, "ONLINE", at))


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.lists(st.tuples(st.integers(0, 1), st.integers(1, 60), st.integers(0, 5)), min_size=1, max_size=8))
def test_hypothesis_allocation_invariants_hold_in_kernel_and_db(db_path, steps):
    """Random allocation attempts: the kernel refuses violations, and the DB sums never exceed credit or requirement."""
    n = next(_COUNTER)
    clock = SequenceClock()
    with SessionLocal() as db:
        _fresh_online(db, n, clock)
        for i, (j, lakh, delta) in enumerate(steps):
            at = clock.next(delta)
            try:
                guarded_run(db, at, lambda k, i=i, j=j, lakh=lakh, at=at: k.allocate(f"HYP-{n}-A{i}", f"CR-HYP-{n}", f"HYP-{n}-{j}", lakh * LAKH,
                                                                              "institution_declaration", at, "finance_reconciliation_officer:anil"))
            except Exception as e:  # noqa: BLE001
                assert type(e).__name__ in ("OverAllocation", "StateError"), e
        used_c = db.scalar(select(func.coalesce(func.sum(m.Allocation.amount_paise), 0)).where(m.Allocation.credit_id == f"CR-HYP-{n}", m.Allocation.active))
        assert used_c <= 50 * LAKH
        for j in range(2):
            used_o = db.scalar(select(func.coalesce(func.sum(m.Allocation.amount_paise), 0)).where(m.Allocation.obligation_id == f"HYP-{n}-{j}", m.Allocation.active))
            assert used_o <= (20 + 10 * j) * LAKH
        # kernel and database agree
        k = LEDGER.kernel()
        assert used_c == 50 * LAKH - k.remaining_on_credit(f"CR-HYP-{n}")


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.integers(1, 10**6))
def test_hypothesis_db_trigger_blocks_any_overallocation_bypassing_kernel(db_path, extra):
    with SessionLocal() as db:
        cap = db.scalar(select(m.BankCredit.amount_paise).where(m.BankCredit.credit_id == "CR-UTR-XYZ-2016-0042"))
        db.add(m.Obligation(obligation_id=f"BY-{extra}", institution_id="INST0003", programme="t", instrument_class="ONLINE", amount_paise=10**12))
        db.flush()
        db.add(m.Allocation(alloc_id=f"BY-{extra}", credit_id="CR-UTR-XYZ-2016-0042", obligation_id=f"BY-{extra}", amount_paise=extra, basis="x"))
        with pytest.raises((IntegrityError, OperationalError, ProgrammingError), match="exceed credit"):
            db.flush()
        db.rollback()
        assert cap == 35 * LAKH


def test_ledger_rolls_back_memory_when_db_refuses(db_path):
    """If storage refuses a write, the in-memory kernel is rebuilt from storage (no divergence)."""
    before = len(LEDGER.kernel().store)
    with SessionLocal() as db:
        pg = db.bind.dialect.name == "postgresql"
        if pg:
            db.execute(text("CREATE FUNCTION tl_test_block() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'blocked for test'; END $$ LANGUAGE plpgsql"))
            db.execute(text("CREATE TRIGGER t_block BEFORE INSERT ON kernel_events FOR EACH ROW EXECUTE FUNCTION tl_test_block()"))
        else:
            db.execute(text("""CREATE TRIGGER t_block BEFORE INSERT ON kernel_events BEGIN SELECT RAISE(ABORT, 'blocked for test'); END"""))
        db.commit()
        with pytest.raises(LedgerError):
            LEDGER.run(db, lambda k: k.record_entitlement("ONL-PQR-UG", "x", datetime.now().isoformat(timespec="seconds"), "section_officer:kiran"))
        db.execute(text("DROP TRIGGER t_block ON kernel_events" if pg else "DROP TRIGGER t_block"))
        db.commit()
    assert len(LEDGER.kernel().store) == before


# ------------------------------------------------------------------ rules
def test_rules_escalate_never_guess(api):
    a = api().login(MEERA, OFF)
    r = a.get("/api/rules/resolve?key=release.fdr_instrument&on_date=2021-06-01").json()
    assert r["status"] == "NOT_SPECIFIED" and not r["usable"] and r["action"].startswith("blocked")
    r = a.get("/api/rules/resolve?key=fdr.manual_renewal_after_maturity&on_date=2018-12-01").json()
    assert r["status"] == "UNVERIFIED" and r["action"] == "escalate to legal cell"
    r = a.get("/api/rules/resolve?key=release.fdr_instrument&on_date=2026-10-01").json()
    assert r["status"] == "RESOLVED" and r["value"] == "noc"
    legal = api().login(LEGAL, OFF)
    assert legal.post("/api/rules/APH-2018-19/confirm", json={"reference": "LC/2026/01"}).status_code == 200
    r = a.get("/api/rules/resolve?key=fdr.manual_renewal_after_maturity&on_date=2018-12-01").json()
    assert r["status"] == "RESOLVED" and r["value"] == "prohibited"
    assert a.post("/api/rules/APH-2018-19/confirm", json={"reference": "x"}).status_code == 403   # only the legal cell


def test_manual_renewal_after_maturity_escalates(api):
    """APH 2024-27 says nothing about renewal after maturity: escalated, not guessed."""
    from app.domain.fdr import submit
    with SessionLocal() as db:
        f = submit(db, inst_id="INST0003", actor="institution:INST0003", bank="PNB", branch="x", instrument_no="MATURED-1", amount_paise=20 * LAKH,
                   rate_bp=700, issue=date(2021, 3, 1), maturity=date(2024, 3, 1), docs=[])
    a = api().login(MEERA, OFF)
    r = a.post(f"/api/fdrs/{f.id}/renewal-check", json={"new_number": "NEW-1", "new_maturity": "2030-01-01"}).json()
    assert r["outcome"] == "ESCALATED_TO_LEGAL_CELL"


def test_renewal_before_maturity_is_replacement(api):
    a = api().login(MEERA, OFF)
    r = a.post("/api/fdrs/FDR202600125/renewal-check", json={"new_number": "NEW-2", "new_maturity": "2031-01-01"}).json()
    assert r["outcome"] == "ACCEPTED_PENDING_BANK_CONFIRMATION"


def test_table_1_4_and_penalty_are_proposals(api):
    a = api().login(MEERA, OFF)
    r = a.post("/api/rules/table-1-4", json={"lines": [{"discipline": "Engineering & Technology", "level": "UG"}, {"discipline": "Management", "level": "PG"}],
                                              "institution_type": "Private-Self Financing", "leased": True}).json()
    assert r["status"] == "PROPOSED" and r["total_paise"] == (35 + 15) * 2 * LAKH and r["proposal_only"]
    assert a.post("/api/rules/table-1-4", json={"lines": [], "institution_type": "Government"}).json()["status"] == "ESCALATED"
    assert a.post("/api/rules/table-1-4", json={"lines": [{"discipline": "Management", "level": "Diploma"}], "institution_type": "Private-Self Financing"}).json()["status"] == "ESCALATED"
    p = a.post("/api/rules/penalty-proposal", json={"principal_paise": 35 * LAKH, "clause": "2.21(i)"}).json()
    assert p["deduction_paise"] == 17_50_000 * 100 and p["proposal_only"]


# ------------------------------------------------------------------ legacy import
def test_legacy_import_never_upgrades_flags_duplicates_blocks_nothing(api):
    anil = api().login(ANIL, OFF)
    body = {"batch_id": "LEG-T1",
            "statement_lines": [{"utr": "OLD-UTR-1", "amount_paise": 20 * LAKH, "value_date": "2012-04-01", "remitter_name": "ABC Engineering College",
                                 "remitter_account": "0001" + "00005010", "narrative": "AICTE-APP-0001"},
                                {"utr": "OLD-UTR-2", "amount_paise": 15 * LAKH, "value_date": "2012-05-01", "remitter_name": "?", "remitter_account": "?", "narrative": ""}],
            "records": [{"legacy_id": "L1", "inst_id": "INST0001", "amount_paise": 20 * LAKH, "instrument_class": "ONLINE", "utr": "OLD-UTR-1"},
                        {"legacy_id": "L2", "inst_id": "INST0003", "amount_paise": 15 * LAKH, "instrument_class": "ONLINE", "utr": "OLD-UTR-2"},
                        {"legacy_id": "L3", "inst_id": "INST0003", "amount_paise": 15 * LAKH, "instrument_class": "ONLINE", "utr": "OLD-UTR-2"},
                        {"legacy_id": "L4", "inst_id": "INST0004", "amount_paise": 9 * LAKH, "instrument_class": "ONLINE"},
                        {"legacy_id": "L5", "inst_id": "INST0005", "amount_paise": 25 * LAKH, "instrument_class": "FDR", "fdr_number": "OLDFD-55", "bank": "PNB"}]}
    r = anil.post("/api/legacy/import", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert all(s["simulated"] for s in out["statement_lines"])
    rep = out["report"]
    assert rep["flagged_duplicate"] == 1 and rep["declared_only"] == 1 and rep["fdr_registered"] == 1 and rep["records"] == 5
    assert "TRACEABLE" not in out["confidence"].values()
    assert out["confidence"]["LEG-L1"] == "CORROBORATED"          # bank remitter account = ABC's registered account
    assert out["confidence"]["LEG-L2"] == "LEGACY_DECLARED"


# ------------------------------------------------------------------ audit chain
def test_audit_verify_clean(api):
    r = api().login(AUDITOR, AUD).post("/api/audit-trail/verify").json()
    assert r["ok"] and r["kernel_chain"]["valid"] and r["portal_chain"]["valid"] and r["checkpoint"]["valid"] and r["replay_matches_live_state"]


def test_audit_detects_edit(api):
    a = api().login(AUDITOR, AUD)
    a.post("/api/sim/audit/tamper", json={"seq": 100, "mode": "edit"})
    r = a.post("/api/audit-trail/verify").json()
    assert not r["ok"] and r["kernel_chain"]["first_bad_seq"] == 100
    assert "edited" in r["kernel_chain"]["problems"][0]["problem"]


def test_audit_detects_deletion_of_last_event_via_checkpoint(api):
    a = api().login(AUDITOR, AUD)
    a.post("/api/sim/audit/tamper", json={"seq": 0, "mode": "delete_last"})
    r = a.post("/api/audit-trail/verify").json()
    assert r["kernel_chain"]["valid"]            # the chain alone cannot see a missing tail ...
    assert r["checkpoint"]["valid"] is False and not r["ok"]   # ... the off-host checkpoint can


def test_audit_detects_middle_deletion_and_relink(db_path, api):
    with SessionLocal() as db:
        db.execute(text("DROP TRIGGER trg_kernel_events_io ON kernel_events" if db.bind.dialect.name == "postgresql" else "DROP TRIGGER trg_kernel_events_no_delete"))
        db.execute(text("DELETE FROM kernel_events WHERE seq = 50"))
        db.commit()
    r = api().login(AUDITOR, AUD).post("/api/audit-trail/verify").json()
    assert not r["ok"] and any("gap" in p["problem"] or "prev-hash" in p["problem"] for p in r["kernel_chain"]["problems"])


# ------------------------------------------------------------------ scenarios S01-S09
@pytest.mark.parametrize("sid", ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09"])
def test_scenario_replay(api, sid):
    r = api().login(MEERA, OFF).post(f"/api/sim/scenarios/{sid}/replay").json()
    assert r["failed"] == 0 and r["passed"] > 0 and r["sandbox"]


# ------------------------------------------------------------------ dashboards come from the database
def test_dashboard_figures_from_db(api):
    a = api().login(MEERA, OFF)
    s = a.get("/api/dashboard/aicte").json()["stats"]
    by = s["by_bucket"]
    assert (by["active"]["count"], by["maturing"]["count"], by["pending"]["count"], by["discrepancy"]["count"], by["released"]["count"],
            by["closed"]["count"]) == (612, 56, 27, 18, 64, 44)
    assert s["total"]["count"] == 821 and s["institutions"] == 482 and s["fdrs_with_discrepancy"] == 18
    # change the data, and the figure follows
    a.post("/api/fdrs/FDR202600126/bank-confirmation")
    a.post("/api/fdrs/FDR202600126/verify", json={})
    s2 = a.get("/api/dashboard/aicte").json()["stats"]
    assert s2["by_bucket"]["pending"]["count"] == 26 and s2["by_bucket"]["active"]["count"] == 613


def test_maturing_counted_from_server_date(db_path):
    with SessionLocal() as db:
        soon = db.scalar(select(func.count()).select_from(m.Fdr).where(m.Fdr.status == "verified", m.Fdr.maturity_date <= date.today() + timedelta(days=90)))
        assert soon == 56


def test_audit_checkpoint_catches_consistent_rewrite_of_head(db_path, api):
    """An insider rewrites the newest event AND recomputes its hash: the chain is self-consistent, so only the
    off-host checkpoint can notice."""
    import json as _json

    from app.ledger import event_data, stored_data
    from trustledger.audit import _digest
    with SessionLocal() as db:
        db.execute(text("DROP TRIGGER trg_kernel_events_io ON kernel_events" if db.bind.dialect.name == "postgresql" else "DROP TRIGGER trg_kernel_events_no_delete"))
        last = db.scalars(select(m.KernelEvent).order_by(m.KernelEvent.seq.desc())).first()
        # the strongest insider: holds the field key too, so the rewrite is consistent after decryption
        data = event_data(last)
        data["rewritten"] = True
        new_hash = _digest(last.seq, last.at, last.type, last.actor, data, last.prev)
        db.execute(text("UPDATE kernel_events SET data = :d, hash = :h WHERE seq = :s"),
                   {"d": stored_data(data), "h": new_hash, "s": last.seq})
        db.commit()
    r = api().login(AUDITOR, AUD).post("/api/audit-trail/verify").json()
    assert r["kernel_chain"]["valid"]
    assert r["checkpoint"]["valid"] is False and "rewritten" in r["checkpoint"]["detail"] and not r["ok"]
