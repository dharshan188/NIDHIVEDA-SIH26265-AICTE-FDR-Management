"""Migration evidence: Alembic to head on (1) a fresh SQLite file, (2) a fresh disposable PostgreSQL 16 database in tl-gap-pg,
(3) a copy of an existing database given as argv[1]. Checks the revision, the new columns, row counts before/after, and a
0006 downgrade/upgrade cycle. Credentials are read from the container into this process only and never printed.

Usage: .venv/bin/python tools/baseline/migration_check.py <existing.db copy>
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import psycopg
import sqlalchemy as sa
from psycopg import sql
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
NEW_COLS = {"content_checks", "integrity_status", "integrity_checked_at"}
TABLES = ["institutions", "users", "fdrs", "fdr_documents", "kernel_events", "portal_events", "notifications", "observations", "field_changes"]


def alembic(url: str, *args: str) -> str:
    env = {**os.environ, "TL_DATABASE_URL": url}
    r = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "alembic", "-c", "alembic.ini", *args], cwd=BACKEND, env=env,
                       capture_output=True, text=True)
    if r.returncode:
        print(r.stdout, r.stderr)
        raise SystemExit(f"alembic {' '.join(args)} failed")
    return (r.stdout + r.stderr).strip()


def state(url: str) -> dict:
    eng = sa.create_engine(url)
    insp = sa.inspect(eng)
    with eng.connect() as c:
        rev = c.execute(sa.text("select version_num from alembic_version")).scalar()
        counts = {t: c.execute(sa.text(f"select count(*) from {t}")).scalar() for t in TABLES if insp.has_table(t)}
    cols = {c["name"] for c in insp.get_columns("fdr_documents")}
    eng.dispose()
    return {"revision": rev, "new_columns": sorted(NEW_COLS & cols), "counts": counts}


def check(label: str, url: str, before: dict | None = None) -> bool:
    print(f"\n== {label}")
    print(alembic(url, "upgrade", "head") or "(alembic upgrade head: no output)")
    s = state(url)
    print("after upgrade head:", json.dumps(s))
    ok = s["revision"] == "0006" and set(s["new_columns"]) == NEW_COLS
    if before is not None:
        same = all(s["counts"].get(t) == n for t, n in before["counts"].items())
        print("row counts preserved:", same)
        ok &= same
    alembic(url, "downgrade", "0005")
    d = state(url)
    print("after downgrade 0005:", d["revision"], "new columns:", d["new_columns"])
    ok &= d["revision"] == "0005" and not d["new_columns"]
    alembic(url, "upgrade", "head")
    u = state(url)
    print("after upgrade head again:", u["revision"], "new columns:", u["new_columns"])
    ok &= u["revision"] == "0006" and set(u["new_columns"]) == NEW_COLS
    print("RESULT", label, "PASS" if ok else "FAIL")
    return ok


def main() -> None:
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        results.append(check("fresh SQLite", f"sqlite:///{tmp}/fresh.db"))

        existing = Path(sys.argv[1]).resolve()
        work = Path(tmp) / "existing.db"
        shutil.copy(existing, work)
        url = f"sqlite:///{work}"
        eng = sa.create_engine(url)
        with eng.connect() as c:
            rev = c.execute(sa.text("select version_num from alembic_version")).scalar()
        eng.dispose()
        before = {"counts": state(url)["counts"]} if rev else None
        print(f"\n(existing database {existing.name}: revision before = {rev}; counts = {json.dumps(before and before['counts'])})")
        results.append(check(f"existing database copy ({existing.name}, from {rev})", url, before))

    obj = json.loads(subprocess.check_output(["docker", "inspect", "tl-gap-pg"]))[0]
    env = dict(i.split("=", 1) for i in obj["Config"]["Env"] if "=" in i)
    user, pw = env["POSTGRES_USER"], env["POSTGRES_PASSWORD"]
    name = "tl_migcheck_" + uuid.uuid4().hex
    admin = psycopg.connect(host="127.0.0.1", port=55433, user=user, password=pw, dbname="postgres", autocommit=True)
    print("\nPostgreSQL", admin.execute("SHOW server_version").fetchone()[0], "disposable database", name)
    admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
    try:
        url = URL.create("postgresql+psycopg", username=user, password=pw, host="127.0.0.1", port=55433, database=name).render_as_string(hide_password=False)
        results.append(check("fresh PostgreSQL 16", url))
    finally:
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()
    print("\nSUMMARY:", "all PASS" if all(results) else "FAILURES", results)
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
