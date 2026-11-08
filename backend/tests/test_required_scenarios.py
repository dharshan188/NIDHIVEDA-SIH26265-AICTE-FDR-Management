"""The six required scenarios, end to end through the API (scripts/required_scenarios.py)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from required_scenarios import run_all  # noqa: E402


def test_six_required_scenarios(api):
    results = run_all(api)
    assert [r["id"] for r in results] == ["R1", "R2", "R3", "R4", "R5", "R6"]
    failed = [(r["id"], c["name"], c["detail"]) for r in results for c in r["checks"] if not c["ok"]]
    assert not failed, failed
