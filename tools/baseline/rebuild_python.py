"""Rebuild the project venv with local CPython; keep the old venv for rollback."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
old = ROOT / ".venv"
backup = ROOT / ".venv-py310-backup"
python = ROOT / ".python/cpython-3.11.17-linux-x86_64-gnu/bin/python3.11"
assert python.is_file(), "Local standalone Python missing"
assert not backup.exists(), "Rollback venv already exists; do not overwrite"
# uv's default launcher is unnecessary. Remove only the link pointing to our new runtime.
launcher = Path.home() / ".local/bin/python3.11"
if launcher.is_symlink() and str(launcher.resolve()).startswith(str(ROOT / ".python")):
    launcher.unlink()
    print("Removed uv-created default-bin launcher; standalone runtime remains entirely under sih2/.", flush=True)
snapshot = subprocess.check_output([str(old / "bin/python"), "-c", "import importlib.metadata as m,json; print(json.dumps({d.metadata['Name']:d.version for d in m.distributions()},sort_keys=True,indent=2))"], text=True)
(ROOT / "docs/verification/session6/python310-packages.json").write_text(snapshot)
old.rename(backup)
print(f"Old venv retained at {backup}", flush=True)
subprocess.run([str(python), "-m", "venv", str(old)], check=True)
subprocess.run([str(old / "bin/python"), "--version"], check=True)
print("New standalone Python venv created; install requirements in the next recorded command.", flush=True)
