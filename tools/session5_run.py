"""Session 5 command capture and read-only kernel integrity verification."""
import datetime
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/verification/session5"
OUT.mkdir(parents=True, exist_ok=True)
label, *command = sys.argv[1:]
if not command:
    raise SystemExit("usage: python3 tools/session5_run.py LABEL COMMAND [ARG ...]")
log = OUT / (label + ".txt")
stamp = datetime.datetime.now().isoformat(timespec="seconds")
with (ROOT / "TEST_REPORT.md").open("a") as report:
    if "## Session 5" not in (ROOT / "TEST_REPORT.md").read_text():
        report.write("\n\n## Session 5 — 2026-10-24\n\nBaseline confirmation before completion work. No earlier result is treated as current-session evidence.\n")
    report.write(f"\n### {label} ({stamp})\n\nWorking directory: `/home/dharshan/sih2`.\n\n```bash\n{shlex.join(command)}\n```\n\n[Complete captured output](docs/verification/session5/{label}.txt).\n")
with log.open("w") as output:
    def emit(value):
        print(value, flush=True)
        output.write(str(value) + "\n")
        output.flush()
    emit("$ " + shlex.join(command))
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end="", flush=True)
        output.write(line)
        output.flush()
    code = process.wait()
    emit(f"Command exit code: {code}")
    kernel = ROOT / "trust-ledger-kernel"
    ignored = {"__pycache__", ".pytest_cache", ".hypothesis"}
    local = {p.relative_to(kernel).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(kernel.rglob("*")) if p.is_file() and not ignored.intersection(p.parts)}
    archive = Path.home() / "Downloads/fdr-trust-ledger-final(2).zip"
    with zipfile.ZipFile(archive) as z:
        expected = {n.removeprefix("trust-ledger-kernel/"): hashlib.sha256(z.read(n)).hexdigest()
                    for n in z.namelist() if n.startswith("trust-ledger-kernel/") and not n.endswith("/")
                    and not ignored.intersection(Path(n).parts)}
    digest = hashlib.sha256(json.dumps(local, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    emit(f"Kernel manifest: {digest}; {len(local)} files; ZIP match: {local == expected}")
    if local != expected or digest != "58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0":
        code = 90
with (ROOT / "TEST_REPORT.md").open("a") as report:
    report.write(f"\nCommand exit: **{process.returncode}**. Kernel manifest after this stage: `{digest}`; ZIP match: **{local == expected}**.\n")
sys.exit(code)
