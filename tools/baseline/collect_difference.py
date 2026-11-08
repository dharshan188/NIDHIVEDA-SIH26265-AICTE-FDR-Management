"""Compare the pre-completion test set with the current suite using real pytest collection.

No historical source snapshot exists: the 'before' test set is explicitly
reconstructed by ignoring Session 4's sole new test module, not called an old checkout.
"""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/verification/session6"
env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONPATH": str(ROOT / "tools/baseline")}
base = [str(ROOT / ".venv/bin/python"), "-m", "pytest", "--collect-only", "-q", "-p", "hypothesis.extra.pytestplugin", "-p", "collection_ids", "tests"]
sets = []
print("Before is a reconstructed test set (current tree, ignoring tests/test_completion.py); no historical source checkout is available.")
print("Collection-only plugin gives byte parameters stable IDs; no tests or assertions are changed.")
for name, extra in (("before", ["--ignore=tests/test_completion.py"]), ("after", [])):
    cmd = base + extra
    print("$ " + " ".join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=ROOT / "backend", env=env, text=True, capture_output=True)
    print(result.stdout, end="", flush=True)
    print(result.stderr, end="", flush=True)
    assert result.returncode == 0
    (OUT / f"collection-{name}.txt").write_text(result.stdout + result.stderr)
    sets.append({s for s in result.stdout.splitlines() if s.startswith("tests/") and "::" in s})
before, after = sets
added, removed = after - before, before - after
print(f"Collected before={len(before)}, after={len(after)}, added={len(added)}, removed={len(removed)}")
print("Added test node IDs:\n" + "\n".join(sorted(added)))
assert len(before) == 137 and len(after) == 147 and len(added) == 10 and not removed
assert all(s.startswith("tests/test_completion.py::") for s in added)
print("PASS: exact ten-test difference; no other collected node IDs changed.")
