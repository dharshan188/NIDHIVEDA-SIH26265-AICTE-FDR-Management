"""Hand-seeded mutants for the backend controls. Each mutant re-inserts ONE control failure into a copy of the
backend; the test suite must fail ("killed"). A survivor means a control is not pinned by a test.

    python scripts/mutants.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MUTANTS = [
    ("IDOR scope check disabled", "app/deps.py", 'if p.user.role == "INSTITUTION" and p.user.institution_id != institution_id:', "if False:"),
    ("CSRF check disabled", "app/deps.py", "if not hmac.compare_digest(sent, s.csrf_token):", "if False:"),
    ("idle timeout disabled", "app/deps.py", "or now - s.last_seen > timedelta(minutes=cfg.session_idle_minutes)", ""),
    ("lockout never triggers", "app/routers/auth.py", "if user.failed_attempts >= cfg.lockout_threshold:", "if False:"),
    ("lock ignored at login", "app/routers/auth.py", "if user and user.locked_until and user.locked_until > now:", "if False:"),
    ("role tab not checked", "app/routers/auth.py", "or user.role != body.role:", ":"),
    ("OTP not marked used", "app/routers/auth.py", '    row.used_at = now\n    return _complete(db, response, p, "otp")', '    return _complete(db, response, p, "otp")'),
    ("OTP expiry ignored", "app/routers/auth.py", "if not row or row.expires_at < now or", "if not row or"),
    ("OTP rate limit removed", "app/routers/auth.py", "if recent >= cfg.otp_max_sends_per_15min:", "if False:"),
    ("DSC serial not bound to user", "app/routers/auth.py", "if serial != p.user.dsc_serial:", "if False:"),
    ("SSO nonce not checked", "app/routers/auth.py", 'if claims.get("nonce") != st.nonce:', "if False:"),
    ("maker-checker removed", "app/domain/release.py", "if rr.scrutiny_by == user.actor:", "if False:"),
    ("approval DSC not checked", "app/domain/release.py", "serial = verify_dsc(certificate_pem, signature_b64, preview[\"approval_message\"])", "serial = user.dsc_serial"),
    ("verify ignores bank mismatch", "app/domain/fdr.py", "    if bad:\n        raise HTTPException(409, {\"error\": \"Mismatch\"", "    if False:\n        raise HTTPException(409, {\"error\": \"Mismatch\""),
    ("verify without bank confirmation", "app/domain/fdr.py", 'if not bv["confirmation"]:', "if False:"),
    ("DB credit cap trigger removed", "app/invariants.py", "            > (SELECT amount_paise FROM bank_credits WHERE credit_id = NEW.credit_id);\n      SELECT RAISE(ABORT, 'INVARIANT: allocations exceed required amount')",
     "            > 1e18;\n      SELECT RAISE(ABORT, 'INVARIANT: allocations exceed required amount')"),
    ("projection ignores bank mismatches", "app/projections.py", "        bad = mismatches(ins, conf)\n        if bad:", "        bad = []\n        if bad:"),
    ("checkpoint not compared", "app/routers/ledger_api.py", "elif row.hash != last[\"hash\"]:", "elif False:"),
    ("chain verify ignores content hash", "app/portal_audit.py", "if _digest(r.seq, r.at, r.type, r.actor, data, r.prev) != r.hash:", "if False:"),
    ("ledger keeps memory after DB failure", "app/ledger.py", "                db.rollback()\n                self.rebuild()", "                db.rollback()"),
    ("institution list not scoped", "app/routers/data.py", "        stmt = stmt.where(m.Fdr.institution_id == p.user.institution_id)", "        pass"),
    ("hold scope check removed", "app/routers/ledger_api.py", "    if not scope:\n        raise HTTPException(422", "    if False:\n        raise HTTPException(422"),
]


def run(tmp: Path) -> bool:
    env = {**os.environ, "PYTHONPATH": "", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "TL_KERNEL_PATH": str(ROOT.parent / "trust-ledger-kernel")}
    env.pop("TL_TEST_PG_URL", None)
    r = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", "-p", "hypothesis.extra.pytestplugin", "tests"], cwd=tmp, env=env,
                       capture_output=True, text=True)
    return r.returncode == 0


def copy() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="tl-mut-"))
    shutil.copytree(ROOT, tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.db*", "uploads", "__pycache__", ".hypothesis", ".pytest_cache"))
    return tmp


def main() -> None:
    # control: the unmutated copy must pass, otherwise every "kill" is meaningless
    tmp = copy()
    ok = run(tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"  control (no mutation): {'PASS' if ok else 'FAIL'}", flush=True)
    if not ok:
        sys.exit("control run failed: results would be invalid")
    killed, survivors = 0, []
    for name, rel, old, new in MUTANTS:
        tmp = copy()
        f = tmp / rel
        src = f.read_text()
        if old not in src:
            print(f"  ERROR  {name}: pattern not found")
            survivors.append(name + " (pattern not found)")
            continue
        f.write_text(src.replace(old, new, 1))
        passed = run(tmp)
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"  {'SURVIVED' if passed else 'killed  '}  {name}", flush=True)
        if passed:
            survivors.append(name)
        else:
            killed += 1
    print(f"\nmutants={len(MUTANTS)} killed={killed} survived={len(survivors)}")
    for s in survivors:
        print("  survivor:", s)


if __name__ == "__main__":
    main()
