"""Run real-service baselines without printing or writing credentials.

Usage: .venv/bin/python tools/baseline/backend_check.py sqlite|postgres|missing
Uses only tl-gap-pg and tl-baseline-s3, never the unrelated PostgreSQL container.
Each run creates a new disposable database; no existing database is reset.
"""
import base64
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid

import psycopg
from psycopg import sql
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]
mode = sys.argv[1]
env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
for name in ("TL_SECRET_KEY", "TL_SIM_BANK_SEED", "TL_PROVIDER_WEBHOOK_SECRET", "TL_OIDC_CLIENT_SECRET"):
    env[name] = secrets.token_urlsafe(48)
env["TL_MASTER_KEY"] = base64.b64encode(secrets.token_bytes(32)).decode()
env["TL_DATA_KEY"] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def inspect_env(name):
    obj = json.loads(subprocess.check_output(["docker", "inspect", name]))[0]
    return dict(item.split("=", 1) for item in obj["Config"]["Env"] if "=" in item)


args = [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q", "-rs", "--tb=short", "-p", "hypothesis.extra.pytestplugin", "--require-services"]
if mode == "missing":
    # A configured, closed local port must fail, even without an explicit mandatory flag.
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        closed_port = sock.getsockname()[1]
    env["TL_TEST_CLAMD"] = f"127.0.0.1:{closed_port}"
    args += ["tests/test_integration_services.py::test_clamav_passes_clean_pdf_and_flags_eicar"]
    print("Required-missing check: TL_TEST_CLAMD points to a closed local port; pytest exit 1 expected.", flush=True)
    result = subprocess.run(args, cwd=ROOT / "backend", env=env)
    print(f"Expected failure observed: {result.returncode == 1}", flush=True)
    sys.exit(0 if result.returncode == 1 else 1)

pg = inspect_env("tl-gap-pg")
s3 = inspect_env("tl-baseline-s3")
user, password = pg["POSTGRES_USER"], pg["POSTGRES_PASSWORD"]
database = "tl_baseline_" + uuid.uuid4().hex
admin = psycopg.connect(host="127.0.0.1", port=55433, user=user, password=password, dbname="postgres", autocommit=True)
version = admin.execute("SHOW server_version").fetchone()[0]
assert version.startswith("16."), f"PostgreSQL 16 required, got {version}"
admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(database)))
env["TL_TEST_PG_URL"] = URL.create("postgresql+psycopg", username=user, password=password, host="127.0.0.1", port=55433, database=database).render_as_string(hide_password=False)
env["TL_TEST_CLAMD"] = "127.0.0.1:3310"
env["TL_TEST_SMTP"] = "127.0.0.1:1025:8025"
env["TL_TEST_S3"] = f"127.0.0.1:8334,{s3['S3_ACCESS_KEY']},{s3['S3_SECRET_KEY']}"
env["TL_TEST_BACKEND"] = mode
env["TL_TEST_PG_CONTAINER"] = "tl-gap-pg"
args += sys.argv[2:] or ["tests"]
print(f"Application fixture backend: {mode}; PostgreSQL {version}; disposable database: {database}", flush=True)
print("Required services: real ClamAV :3310, SeaweedFS :8334, Mailpit SMTP :1025 / HTTP :8025, PostgreSQL :55433", flush=True)
print("Credentials loaded into child environment only (redacted). Command: python -m pytest " + " ".join(args[3:]), flush=True)
try:
    # Even exception tracebacks must not put generated keys or service credentials in logs.
    private = [env[n] for n in ("TL_MASTER_KEY", "TL_DATA_KEY", "TL_SECRET_KEY", "TL_SIM_BANK_SEED", "TL_PROVIDER_WEBHOOK_SECRET", "TL_OIDC_CLIENT_SECRET")]
    private += [password, s3["S3_ACCESS_KEY"], s3["S3_SECRET_KEY"]]
    result = subprocess.Popen(args, cwd=ROOT / "backend", env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in result.stdout:
        for value in private:
            line = line.replace(value, "[REDACTED]")
        print(line, end="", flush=True)
    result.wait()
finally:
    admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
    admin.close()
sys.exit(result.returncode)
