"""Comparison against a conventional status-field workflow, plus synthetic load.

Everything here is SYNTHETIC. Error rates in the generated data are assumptions chosen
to exercise the controls; they are not AICTE statistics. What is measured for real:
how each design behaves on the same inputs, and how fast the kernel runs.
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trustledger.baseline import ConventionalWorkflow  # noqa: E402
from trustledger.crypto import TestBankSigner  # noqa: E402
from trustledger.kernel import Kernel, lakh  # noqa: E402
from trustledger.scenario import load_scenario, make_policy, Runner  # noqa: E402

SEED = 26265
ASSUMPTIONS = {
    "legacy_records": 10_000, "institutions": 2_000,
    "p_statement_line_with_utr": 0.70, "p_remitter_on_statement_line": 0.50,
    "p_no_reference": 0.25, "p_reference_not_in_statement": 0.05,
    "p_recorded_against_wrong_institution": 0.02, "p_duplicate_record": 0.01, "p_two_institutions_claim_one_utr": 0.01,
    "refunds": 2_000, "p_return_before_confirmation": 0.03, "p_return_after_confirmation": 0.002,
}


def decisive_cases():
    """Same eight situations, run through both designs. TL results come from the scenario files."""
    b = ConventionalWorkflow()
    rows = []

    b.create_obligation("O1", "A", 35); b.record_debit("R1", "UTR1"); b.record_return("R1")
    rows.append(("Rs 35 lakh RTGS refund returned after debit + UTR", "S01",
                 "liability reopened, not Completed", f"shows '{b.refund_status['R1']}' (false completion)"))
    b.create_obligation("O-UG", "A", 35); b.create_obligation("O-PG", "A", 15)
    ok1, ok2 = b.link_credit("UTR-50L", "O-UG"), b.link_credit("UTR-50L", "O-PG")
    rows.append(("One Rs 50 lakh UTR for Rs 35 + 15 lakh obligations", "S03",
                 "both funded, nothing duplicated", "second obligation rejected as duplicate UTR" if ok1 and not ok2 else "?"))
    b.create_obligation("L1", "A", 20); b.migrate("L1")
    rows.append(("Legacy Rs 20 lakh credit, owner not provable", "S04", "shown as declared / uncertain, not certified",
                 "migrated record shows Verified" if b.verified["L1"] else "?"))
    b.create_obligation("OA1", "A", 35); b.create_obligation("OB1", "B", 15); b.hold_institution("A")
    rows.append(("Contested item touches A; A's other Rs 35 lakh is proven", "S05", "A's proven Rs 35 lakh releasable",
                 "all of A blocked" if not b.can_release("OA1") else "?"))
    b.create_obligation("OF", "C", 15); b.register_fdr("OF", "PNB-FD-1001")
    rows.append(("FDR auto-renewed in 2019 to a new number; NOC in 2026", "S06", "NOC names PNB-FD-2207 after fresh bank check",
                 f"NOC names {b.noc_instrument('OF')} (superseded number)"))
    rows.append(("Manual renewal after maturity under a prohibiting edition", "S07", "rejected with clause cited",
                 "accepted" if b.renewal_allowed() else "?"))
    rows.append(("Bank key compromised from a past date", "S09", "dependent evidence untrusted, payment stopped",
                 "evidence still trusted" if b.evidence_still_trusted() else "?"))
    rows.append(("Approver tried to bypass a mandatory check on this case", "S10", "approver blocked (conflict of interest)",
                 "no notion of case handlers"))
    out = []
    for title, sid, correct, base in rows:
        path = next((ROOT / "scenarios").glob(f"{sid}_*.json"))
        sc = load_scenario(path)
        res = Runner(policy=make_policy(sc.get("policy_overrides"))).run(sc)
        out.append({"case": title, "correct": correct, "baseline": base,
                    "trust_ledger": f"{sid}: {res['passed']} checks passed, {res['failed']} failed"})
    return out


def migration_bench():
    rnd = random.Random(SEED)
    A = ASSUMPTIONS
    k = Kernel()
    bank = TestBankSigner("SBI", "SBI-K1")
    k.register_signer("SBI-K1", "SBI", bank.public_key_b64, "2000-01-01", "2000-01-01T00:00")
    insts = [f"I{i:04d}" for i in range(A["institutions"])]
    for i in insts:
        k.register_institution(i, f"Institute {i}", "2000-01-02T00:00", known_accounts=[f"ACC-{i}"])
    records, truth, n = [], {}, 0
    at = "2012-01-01T00:00"
    statement = []
    for r in range(A["legacy_records"]):
        owner = rnd.choice(insts)
        recorded = owner if rnd.random() >= A["p_recorded_against_wrong_institution"] else rnd.choice([x for x in insts if x != owner])
        amt = lakh(rnd.choice([5, 15, 35]))
        u = rnd.random()
        rec = {"legacy_id": f"R{r}", "inst_id": recorded, "amount": amt, "instrument_class": "ONLINE"}
        if u < A["p_statement_line_with_utr"]:
            utr = f"U{r}"
            pay = {"utr": utr, "amount": amt, "value_date": "2012-01-01", "narrative": "SD"}
            if rnd.random() < A["p_remitter_on_statement_line"]:
                pay["remitter_account"] = f"ACC-{owner}"
            statement.append(pay)
            rec["utr"] = utr
        elif u < A["p_statement_line_with_utr"] + A["p_reference_not_in_statement"]:
            rec["utr"] = f"MISSING{r}"
        records.append(rec)
        truth[f"LEG-R{r}"] = owner
    # duplicates and shared-UTR claims (ground truth: they create no new money)
    extra = []
    linked = [x for x in records if x.get("utr", "").startswith("U")]
    for x in rnd.sample(linked, int(A["legacy_records"] * A["p_duplicate_record"])):
        extra.append({**x, "legacy_id": x["legacy_id"] + "-DUP"}); truth[f"LEG-{x['legacy_id']}-DUP"] = None
    for x in rnd.sample(linked, int(A["legacy_records"] * A["p_two_institutions_claim_one_utr"])):
        other = rnd.choice([i for i in insts if i != x["inst_id"]])
        extra.append({**x, "legacy_id": x["legacy_id"] + "-CLAIM", "inst_id": other}); truth[f"LEG-{x['legacy_id']}-CLAIM"] = None
    t0 = time.perf_counter()
    for p in statement:
        n += 1
        k.record_bank_evidence(f"S{n}", bank.sign("credit_advice", p, at), at)
    report = k.import_legacy("BENCH", records + extra, "2026-08-01T00:00")
    elapsed = time.perf_counter() - t0

    certified_wrong = certified = 0
    for aid, a in k.allocations.items():
        if not a["active"]:
            continue
        conf = k.allocation_confidence(aid)
        if conf in ("TRACEABLE", "CORROBORATED"):
            certified += 1
            if truth.get(a["obligation_id"]) != k.obligations[a["obligation_id"]]["inst_id"]:
                certified_wrong += 1
    wrong_records = sum(1 for oid, owner in truth.items() if owner and k.obligations[oid]["inst_id"] != owner)
    wrong_detected = wrong_uncertified = 0
    by_conf = {}
    for aid, a in k.allocations.items():
        if not a["active"]:
            continue
        conf = k.allocation_confidence(aid)
        by_conf[conf] = by_conf.get(conf, 0) + 1
        owner = truth.get(a["obligation_id"])
        if owner and owner != k.obligations[a["obligation_id"]]["inst_id"]:
            if conf == "UNCERTAIN":
                wrong_detected += 1
            elif conf not in ("TRACEABLE", "CORROBORATED"):
                wrong_uncertified += 1
    wrong_declared_only = sum(1 for oid, owner in truth.items() if owner and k.obligations[oid]["inst_id"] != owner and k.obligations[oid]["legacy_declared"])
    no_bank_evidence = report["declared_only"]
    dup_amount = sum(x["amount"] for x in extra if x["legacy_id"].endswith("-DUP"))
    insts_with_deposits = len({o["inst_id"] for o in k.obligations.values()})
    insts_to_confirm = len({c["inst_id"] for c in k.confirmation_requests()})
    t1 = time.perf_counter()
    ok, _ = k.store.verify()
    t_verify = time.perf_counter() - t1
    t2 = time.perf_counter()
    same = Kernel.replay(k.store, k.policy, k._packs).snapshot() == k.snapshot()
    t_replay = time.perf_counter() - t2
    return {
        "records_imported": report["records"], "import_report": report, "events": len(k.store),
        "import_seconds": round(elapsed, 2), "chain_verify_seconds": round(t_verify, 2), "replay_seconds": round(t_replay, 2),
        "chain_valid": ok, "replay_identical": same,
        "records_against_wrong_institution_in_input": wrong_records,
        "baseline_marked_verified": report["records"], "baseline_verified_but_wrong_owner": wrong_records,
        "baseline_verified_without_bank_evidence": no_bank_evidence,
        "baseline_liability_overstated_by_duplicates_lakh": dup_amount / lakh(1),
        "tl_certified_by_bank_evidence": certified, "tl_certified_but_wrong_owner": certified_wrong,
        "tl_duplicates_flagged_not_added": report["flagged_duplicate"], "tl_disputes_opened": report["disputed"],
        "tl_blocked_at_import": len(k.holds), "tl_resubmission_requests_at_import": 0,
        "tl_allocations_by_confidence": by_conf, "tl_items_declared_without_bank_trace": no_bank_evidence,
        "tl_wrong_owner_auto_flagged_uncertain": wrong_detected, "tl_wrong_owner_not_detected_but_not_certified": wrong_uncertified + wrong_declared_only,
        "v4_annual_confirmation_institutions": insts_with_deposits, "v4_annual_confirmation_items": len(k.obligations),
        "v5_institutions_contacted": insts_to_confirm, "v5_items_contacted": len(k.confirmation_requests()),
    }


def payment_bench():
    rnd = random.Random(SEED + 1)
    A = ASSUMPTIONS
    k = Kernel()
    bank = TestBankSigner("SBI", "SBI-K1")
    k.register_signer("SBI-K1", "SBI", bank.public_key_b64, "2000-01-01", "2000-01-01T00:00")
    n = 0

    def ev(kind, p, at):
        nonlocal n
        n += 1
        k.record_bank_evidence(f"E{n}", bank.sign(kind, p, at), at)

    t0 = time.perf_counter()
    received = {}
    false_complete_tl = 0
    baseline = ConventionalWorkflow()
    t = "2026-01-01T10:00"   # one business day; time only needs to be non-decreasing here
    for i in range(A["refunds"]):
        inst, oid, amt = f"I{i}", f"O{i}", lakh(rnd.choice([5, 15, 35]))
        k.register_institution(inst, f"Institute {i}", t, known_accounts=[f"ACC-{i}"])
        k.create_obligation(oid, inst, "UG", amt, "ONLINE", t, reference=f"REF{i}")
        ev("credit_advice", {"utr": f"D{i}", "amount": amt, "value_date": t[:10], "narrative": f"REF{i}"}, t)
        k.allocate(f"A{i}", f"CR-D{i}", oid, amt, "machine_reference", t, "system:auto")
        k.record_entitlement(oid, "closure", t, "section_officer:kiran")
        k.record_affidavit(oid, "AFFIDAVIT-6", True, t, "section_officer:kiran")
        k.register_payee(inst, f"ACC-{i}", "IFSC1", f"Institute {i}", t, f"institution:{inst}")
        ev("name_lookup", {"account": f"ACC-{i}", "ifsc": "IFSC1", "name_at_bank": f"Institute {i}"}, t)
        k.authorise_release(f"R{i}", oid, t, "deputy_director:meera")
        k.initiate_payment(f"R{i}", t, "finance_officer:ravi")
        ev("debit_advice", {"refund_id": f"R{i}", "utr": f"P{i}", "amount": amt}, t)
        baseline.record_debit(f"R{i}", f"P{i}")
        u = rnd.random()
        if u < A["p_return_before_confirmation"]:
            ev("return_advice", {"original_utr": f"P{i}", "return_utr": f"RT{i}", "amount": amt, "reason_code": "BENEFICIARY_BANK_REJECT", "returned_at": t}, t)
            received[f"R{i}"] = False
        else:
            ev("credit_confirmation", {"utr": f"P{i}", "credited_at": t, "amount": amt, "beneficiary_account": f"ACC-{i}"}, t)
            received[f"R{i}"] = True
            if u > 1 - A["p_return_after_confirmation"]:
                ev("return_advice", {"original_utr": f"P{i}", "return_utr": f"RT{i}", "amount": amt, "reason_code": "CREDIT_REVERSED_BY_BENEFICIARY_BANK", "returned_at": t}, t)
                received[f"R{i}"] = False
    elapsed = time.perf_counter() - t0
    for rid, got_money in received.items():
        if "Completed" in k.refund_status_text(rid) and not got_money:
            false_complete_tl += 1
    false_complete_base = sum(1 for rid, got in received.items() if baseline.refund_status[rid] == "Completed" and not got)
    return {"refunds": A["refunds"], "returned_in_input": sum(not v for v in received.values()),
            "baseline_false_completed": false_complete_base, "tl_false_completed": false_complete_tl,
            "tl_reopened_liabilities": sum(1 for r in k.refunds.values() if r["state"] == "REISSUE_REQUIRED"),
            "events": len(k.store), "seconds": round(elapsed, 2), "chain_valid": k.store.verify()[0]}


if __name__ == "__main__":
    result = {"assumptions_synthetic": ASSUMPTIONS, "decisive_cases": decisive_cases(), "migration": migration_bench(), "payments": payment_bench()}
    out = ROOT / "results" / "compare_and_bench.json"
    out.write_text(json.dumps(result, indent=2))
    print("DECISIVE CASES (same inputs, two designs)")
    for r in result["decisive_cases"]:
        print(f"- {r['case']}\n    correct: {r['correct']}\n    baseline: {r['baseline']}\n    trust ledger: {r['trust_ledger']}")
    print("\nMIGRATION (synthetic)")
    for kk, v in result["migration"].items():
        print(f"  {kk}: {v}")
    print("\nPAYMENTS (synthetic)")
    for kk, v in result["payments"].items():
        print(f"  {kk}: {v}")
