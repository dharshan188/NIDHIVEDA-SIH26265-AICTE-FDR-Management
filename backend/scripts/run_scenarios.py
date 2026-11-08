"""Replay the reviewer scenarios S01-S09 (kernel JSON fixtures) with the kernel's own runner.

    python scripts/run_scenarios.py            # S01-S09
    python scripts/run_scenarios.py S01 S06    # selected
    python scripts/run_scenarios.py --log      # print every step

Each scenario runs in a fresh sandbox kernel; the database is not touched. Exit code 1 if any check fails.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402

get_settings()   # puts the kernel on sys.path

from trustledger.scenario import SCENARIO_DIR, Runner, load_scenario, make_policy  # noqa: E402

DEFAULT = ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09"]


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ids = args or DEFAULT
    failed = passed = 0
    for sid in ids:
        sc = load_scenario(next(SCENARIO_DIR.glob(f"{sid}_*.json")))
        res = Runner(policy=make_policy(sc.get("policy_overrides"))).run(sc)
        passed += res["passed"]
        failed += res["failed"]
        print(f"{sid}  {'OK  ' if not res['failed'] else 'FAIL'}  {res['passed']:>3} passed  {res['failed']} failed   {sc['title']}")
        if "--log" in sys.argv or res["failed"]:
            print("\n".join("      " + line for line in res["log"]))
    print(f"\nscenarios={len(ids)} checks_passed={passed} checks_failed={failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
