"""Read-only final integrity, container inventory and disk-space evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

root = Path(__file__).resolve().parents[2]
kernel = root / "trust-ledger-kernel"
ignored = {"__pycache__", ".pytest_cache", ".hypothesis"}
local = {p.relative_to(kernel).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(kernel.rglob("*")) if p.is_file() and not ignored.intersection(p.parts)}
before = json.loads((root / "docs/verification/baseline-resume/kernel-manifest-before.json").read_text())
archive = Path.home() / "Downloads/fdr-trust-ledger-final(2).zip"
with zipfile.ZipFile(archive) as z:
    expected = {n.removeprefix("trust-ledger-kernel/"): hashlib.sha256(z.read(n)).hexdigest()
                for n in z.namelist() if n.startswith("trust-ledger-kernel/") and not n.endswith("/")
                and not ignored.intersection(Path(n).parts)}
assert local == before == expected
print("Final original kernel matches before-mutation manifest and ZIP:", len(local), "files", flush=True)
print("Canonical manifest SHA-256:", hashlib.sha256(json.dumps(local, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), flush=True)
print("ZIP archive SHA-256:", hashlib.sha256(archive.read_bytes()).hexdigest(), flush=True)
print("Earlier rmdir removed empty docs/verification/final-baseline, docs/verification, docs only.", flush=True)
print("Kernel docs directory exists:", (kernel / "docs").exists(), flush=True)
for args in (
    ["git", "rev-parse", "--show-toplevel"],
    ["docker", "ps", "-a", "--format", "{{.Names}} {{.Image}} {{.Status}} {{.Ports}}"],
    ["docker", "exec", "tl-gap-pg", "pg_isready"],
    ["docker", "exec", "tl-baseline-s3", "du", "-sh", "/data"],
    ["df", "-h", "/"],
):
    print("$ " + " ".join(args), flush=True)
    subprocess.run(args, cwd=root, check=True)
