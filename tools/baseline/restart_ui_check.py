"""Restart only the Session 6 UI-check server; carry keys in memory, never in a file."""
import os
from pathlib import Path
import re
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
listeners = subprocess.check_output(["ss", "-ltnpH", "sport = :8001"], text=True)
pid = int(re.search(r"pid=(\d+)", listeners).group(1))
proc = Path(f"/proc/{pid}")
assert "uvicorn" in (proc / "cmdline").read_bytes().decode().replace("\0", " ")
environment = dict(x.split("=", 1) for x in (proc / "environ").read_bytes().decode().split("\0") if "=" in x)
assert environment.get("TL_UI_WORK") == str(ROOT / ".ui-check/session6-ui"), "Not our Session 6 test instance"
parent = int(next(s.split()[1] for s in (proc / "status").read_text().splitlines() if s.startswith("PPid:")))
assert "tools/ui-checks/serve.py" in Path(f"/proc/{parent}/cmdline").read_bytes().decode().replace("\0", " ")
print(f"Stopping own Session 6 server parent {parent}; credentials carried only in process memory.", flush=True)
os.kill(parent, signal.SIGTERM)
for _ in range(50):
    if not subprocess.check_output(["ss", "-ltnH", "sport = :8001"], text=True).strip():
        break
    time.sleep(.2)
print("Restarting without --reset; database and environment keys preserved.", flush=True)
subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "tools/ui-checks/serve.py"), "--reload"], cwd=ROOT, env=environment, check=True)
