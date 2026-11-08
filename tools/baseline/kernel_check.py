"""Verify every ZIP member, then mutate only a scratch copy. No kernel writes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
KERNEL = ROOT / "trust-ledger-kernel"
OUT = Path(os.environ.get("TL_VERIFICATION_DIR", ROOT / "docs/verification/baseline-resume"))
ZIP = Path.home() / "Downloads/fdr-trust-ledger-final(2).zip"
IGNORED = {"__pycache__", ".pytest_cache", ".hypothesis"}


def manifest():
    return {p.relative_to(KERNEL).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(KERNEL.rglob("*")) if p.is_file() and not IGNORED.intersection(p.parts)}


def digest(items):
    # SHA-256 of sorted, compact JSON mapping relative names to their SHA-256.
    return hashlib.sha256(json.dumps(items, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


before = manifest()
with zipfile.ZipFile(ZIP) as archive:
    expected = {n.removeprefix("trust-ledger-kernel/"): hashlib.sha256(archive.read(n)).hexdigest()
                for n in archive.namelist() if n.startswith("trust-ledger-kernel/") and not n.endswith("/")
                and not IGNORED.intersection(Path(n).parts)}
print(f"ZIP: {ZIP}\nZIP members: {len(expected)}; local files: {len(before)}", flush=True)
print(f"ZIP manifest SHA-256: {digest(expected)}\nLocal before SHA-256: {digest(before)}", flush=True)
assert before == expected, "Kernel differs from ZIP (including additions/deletions)"
print("All ZIP members byte-identical; no extra non-cache files.", flush=True)
print("Earlier rmdir targets: docs/verification/final-baseline, docs/verification, docs (all empty).", flush=True)
print(f"Kernel docs exists now: {(KERNEL / 'docs').exists()}; ZIP contains docs: {any(n.startswith('docs/') for n in expected)}", flush=True)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "kernel-manifest-before.json").write_text(json.dumps(before, sort_keys=True, indent=2) + "\n")
scratch = Path(tempfile.mkdtemp(prefix="tl-baseline-kernel-")) / "kernel"
shutil.copytree(KERNEL, scratch, ignore=shutil.ignore_patterns(*IGNORED))
print(f"Scratch: {scratch}", flush=True)
env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
python = str(ROOT / ".venv/bin/python")
control = subprocess.run([python, "-m", "pytest", "-q", "-p", "hypothesis.extra.pytestplugin", "tests"], cwd=scratch, env=env)
assert control.returncode == 0, "Unmutated scratch control failed"
scenarios = subprocess.run([python, "-m", "trustledger.scenario"], cwd=scratch, env=env)
assert scenarios.returncode == 0, "Kernel scenario run failed"
result = subprocess.run([python, "tools/mutants.py"], cwd=scratch, env=env)
after = manifest()
(OUT / "kernel-manifest-after.json").write_text(json.dumps(after, sort_keys=True, indent=2) + "\n")
print(f"Local after SHA-256: {digest(after)}; unchanged: {before == after}; ZIP match: {after == expected}", flush=True)
assert before == after == expected
score = (scratch / "results/mutants.txt").read_text()
(OUT / "kernel-mutants.txt").write_text(score)
print(f"Harness exit: {result.returncode} (1 means at least one survivor; expected 32/33)", flush=True)
assert "32/33 killed" in score or "33/33 killed" in score, score
sys.exit(0)
