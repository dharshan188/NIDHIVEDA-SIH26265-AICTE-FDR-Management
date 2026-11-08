"""Hand-seeded mutation testing.

Each mutant re-introduces one specific control failure (several are exactly the bugs the
round-4 reviewer described). The suite must FAIL for each mutant ("killed").
A surviving mutant means a control is not actually protected by a test.

This is a targeted harness, not an exhaustive tool such as mutmut: we chose the mutants.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MUTANTS = [
    ("Refund marked settled at bank debit (reviewer Issue 1)", "trustledger/kernel.py",
     'r["state"] = "DEBITED"', 'r["state"] = "SETTLED"'),
    ("Returned payment does not reopen the attempt", "trustledger/kernel.py",
     'att.update(status="RETURNED"', 'att.update(status=att["status"]'),
    ("Allocation may exceed money received", "trustledger/kernel.py",
     'if amount > self.remaining_on_credit(credit_id):', 'if False:'),
    ("Obligation may be over-funded", "trustledger/kernel.py",
     'if self.allocated_to(obligation_id) + amount > o["amount"]:', 'if False:'),
    ("Release counts declared money as proven", "trustledger/kernel.py",
     'sufficient = sum(fb[k] for k in self.policy["release"]["online_sufficient_confidence"])\n            dec.releasable',
     'sufficient = sum(v for kk, v in fb.items() if kk not in ("HELD",))\n            dec.releasable'),
    ("Holds ignored", "trustledger/kernel.py",
     'if h["status"] != "ACTIVE":\n                continue', 'if True:\n                continue'),
    ("Compromised signer still trusted", "trustledger/kernel.py",
     'if s["compromised_from"] and when >= s["compromised_from"]:', 'if False:'),
    ("Signer validity judged at the (forgeable) signed_at", "trustledger/kernel.py",
     'ok, why = self._signer_valid_at(envelope["key_id"], at)', 'ok, why = self._signer_valid_at(envelope["key_id"], envelope["signed_at"])'),
    ("Stale FDR evidence accepted (age)", "trustledger/kernel.py",
     'if age > max_age:', 'if False:'),
    ("Evidence older than last maturity accepted", "trustledger/kernel.py",
     'and last["as_of"][:10] < ins["maturity_date"]:', 'and False:'),
    ("Unverified rule pack applied silently", "trustledger/rules.py",
     '"RESOLVED" if verified else "UNVERIFIED"', '"RESOLVED"'),
    ("Conflict-of-interest check removed", "trustledger/kernel.py",
     'coi = approver in self.handlers.get(obligation_id, set())', 'coi = False'),
    ("Mandatory clearance can be overridden", "trustledger/kernel.py",
     'if code not in self.policy["admin_checks"]:', 'if False:'),
    ("Account-related return does not force payee re-verification", "trustledger/kernel.py",
     'if needs_payee:\n                self.payees', 'if False:\n                self.payees'),
    ("Returned money can be re-used as a new deposit", "trustledger/kernel.py",
     'if c["kind"] != "deposit":', 'if False:'),
    ("Machine-reference basis not checked", "trustledger/kernel.py",
     'if basis == "machine_reference" and (not o["reference"] or o["reference"] not in re.split(r"[^A-Za-z0-9-]+", c["narrative"])):', 'if False:'),
    ("Remitter from another institution not flagged", "trustledger/kernel.py",
     'if owner and owner != self.obligations[a["obligation_id"]]["inst_id"] and self.evidence_valid(rem_ev):', 'if False:'),
    ("Hash excludes previous hash", "trustledger/audit.py",
     '"data": data, "prev": prev})', '"data": data, "prev": ""})'),
    ("Payment re-issue skips evidence re-check", "trustledger/kernel.py",
     'bad = [e for e in r["relied_evidence"] if not self.evidence_valid(e)]', 'bad = []'),
    ("Policy hold-scope rule ignored (institution-wide holds allowed)", "trustledger/kernel.py",
     'if hp["scope"] == "affected_items_only" and (set(scope) - {"allocations", "credits", "instruments"}):', 'if False:'),
    ("V6-T01 other bank may settle a payment", "trustledger/kernel.py",
     'if env["bank"] != self.evidence[att["debit_evidence"]]["bank"]:', 'if False:'),
    ("V6-T03 dispute award may over-fund", "trustledger/kernel.py",
     'raise OverAllocation(f"award would over-fund obligation {oid}")', 'pass'),
    ("V6-T06 substring reference match", "trustledger/kernel.py",
     'o["reference"] not in re.split(r"[^A-Za-z0-9-]+", c["narrative"])', 'o["reference"] not in c["narrative"]'),
    ("V6-T07 invalid pool evidence still matches", "trustledger/kernel.py",
     'bool(bank) and self.evidence_valid(bank["evidence_id"]) and', 'bool(bank) and'),
    ("V7-1 other bank may confirm an FDR", "trustledger/kernel.py",
     'return "instrument confirmation must come from the instrument\'s issuing bank"', 'pass'),
    ("V7-3 payment UTR reuse allowed", "trustledger/kernel.py",
     'return "payment UTR already used by another payment attempt"', 'pass'),
    ("V7-4 case id reuse allowed", "trustledger/kernel.py",
     'raise StateError(f"case id {case_id} already used")', 'pass'),
    ("R8-T16 FDR principal mismatch ignored", "trustledger/kernel.py",
     'if last["amount"] != ins["amount"]:', 'if False:'),
    ("R8-T17 obligation id reuse allowed", "trustledger/kernel.py",
     'self._unique("obligation", obligation_id, self.obligations)', 'pass'),
    ("R8-T18 instrument id reuse allowed", "trustledger/kernel.py",
     'self._unique("instrument", instrument_id, self.instruments)', 'pass'),
    ("R8-T19 second NOC allowed", "trustledger/kernel.py",
     'raise StateError(f"NOC {live[0]} already issued for this obligation; supersede or cancel it formally")', 'pass'),
    ("R8-T20 confirmation amount not checked", "trustledger/kernel.py",
     'if p.get("amount") != att["amount"]:', 'if False:'),
    ("R8-T20 confirmation beneficiary not checked", "trustledger/kernel.py",
     'if p.get("beneficiary_account") != att["beneficiary_account"]:', 'if False:'),
]


def run_suite(cwd: Path) -> bool:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "tests"], cwd=cwd,
                       capture_output=True, text=True)
    return r.returncode == 0


def main() -> int:
    results = []
    for name, rel, old, new in MUTANTS:
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "k"
            shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns("results", "__pycache__", ".hypothesis", ".pytest_cache"))
            f = dst / rel
            src = f.read_text()
            if src.count(old) != 1:
                results.append((name, "NOT APPLIED (pattern count %d)" % src.count(old)))
                continue
            f.write_text(src.replace(old, new))
            survived = run_suite(dst)
            results.append((name, "SURVIVED" if survived else "killed"))
            print(f"{'SURVIVED' if survived else 'killed  '}  {name}", flush=True)
    killed = sum(1 for _, s in results if s == "killed")
    print(f"\n{killed}/{len(results)} mutants killed")
    (ROOT / "results" / "mutants.txt").write_text("\n".join(f"{s:<10} {n}" for n, s in results) + f"\n\n{killed}/{len(results)} killed\n")
    return 0 if killed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
