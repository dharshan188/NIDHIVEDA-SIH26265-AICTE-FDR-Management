"""Runs the six required scenarios against a fresh, seeded throwaway database and writes the scenario report.

  python scripts/run_required_scenarios.py            -> prints a summary, writes docs/scenario-report.{md,json}
Exit code 1 if any check fails.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="tl-required-"))
os.environ.update({"TL_ENV": "dev", "TL_DATABASE_URL": f"sqlite:///{TMP / 'run.db'}", "TL_CHECKPOINT_PATH": str(TMP / "cp.jsonl"),
                   "TL_DEMO_PASSWORD": "Demo-Pass-2026!", "TL_API_URL": "https://testserver/api", "TL_DEVCERTS_DIR": str(TMP / "devcerts"),
                   "TL_OBJECT_DIR": str(TMP / "objects"), "TL_SCANNER": "stub", "TL_OBJECT_STORE": "fs"})
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from fastapi.testclient import TestClient  # noqa: E402

from app import invariants  # noqa: E402
from app.db import Base, SessionLocal, make_engine, set_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed import seed_all  # noqa: E402
from required_scenarios import run_all  # noqa: E402

PW = os.environ["TL_DEMO_PASSWORD"]


class Api:
    def __init__(self, app):
        self.c = TestClient(app, base_url="https://testserver")
        self.c.headers["X-TL-Client"] = "web"

    def login(self, username: str, role: str, method: str = "otp"):
        assert self.c.post("/api/auth/login", json={"username": username, "password": PW, "role": role}).status_code == 200
        if method == "otp":
            self.c.post("/api/auth/otp/send")
            code = self.c.get(f"/api/sim/otp-outbox/{username}").json()["code"]
            r = self.c.post("/api/auth/otp/verify", json={"code": code})
        else:
            code = self.c.get(f"/api/sim/totp/{username}").json()["code"]
            r = self.c.post("/api/auth/totp/verify", json={"code": code})
        self.c.headers["X-CSRF-Token"] = r.json()["user"]["csrf_token"]
        return self

    def dsc(self, username: str, message: str) -> dict:
        return self.c.post("/api/sim/dsc/sign", json={"username": username, "message": message}).json()

    def __getattr__(self, name):
        return getattr(self.c, name)


def main() -> int:
    eng = make_engine(os.environ["TL_DATABASE_URL"])
    Base.metadata.create_all(eng)
    with eng.begin() as c:
        invariants.install(c)
    set_engine(eng)
    with SessionLocal() as db:
        seed_all(db)
    app = create_app(start_scheduler=False)
    results = run_all(lambda: Api(app))
    passed, failed = sum(r["passed"] for r in results), sum(r["failed"] for r in results)
    for r in results:
        print(f"{r['id']}  {'OK  ' if not r['failed'] else 'FAIL'} {r['passed']:>2} passed  {r['title']}")
        for c in r["checks"]:
            if not c["ok"]:
                print(f"      FAILED: {c['name']} — {c['detail']}")
    print(f"scenarios={len(results)} checks_passed={passed} checks_failed={failed}")
    docs = ROOT.parent / "docs"
    docs.mkdir(exist_ok=True)
    stamp = datetime.now().isoformat(timespec="seconds")
    (docs / "scenario-report.json").write_text(json.dumps({"generated_at": stamp, "passed": passed, "failed": failed, "scenarios": results}, indent=1,
                                                           ensure_ascii=False))
    lines = ["# Required scenarios — report", "", f"Generated {stamp} by `backend/scripts/run_required_scenarios.py` against a fresh seeded "
             "database. Bank, OTP/DSC, SMS/e-mail/WhatsApp/push providers, the malware-scanner stub and the clock are SIMULATED; document storage uses a local filesystem. Real-service tests run separately.", "",
             f"**{len(results)} scenarios, {passed} checks passed, {failed} failed.**", ""]
    for r in results:
        lines += [f"## {r['id']} — {r['title']}", "", "| Check | Result |", "|---|---|"]
        lines += [f"| {c['name']} | {'pass' if c['ok'] else 'FAIL: ' + c['detail'].replace('|', '/')} |" for c in r["checks"]]
        lines.append("")
    (docs / "scenario-report.md").write_text("\n".join(lines))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
