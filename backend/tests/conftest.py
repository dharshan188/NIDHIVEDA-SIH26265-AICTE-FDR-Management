from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import uuid
from contextlib import contextmanager, ExitStack
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_TMP = Path(tempfile.mkdtemp(prefix="tl-tests-"))
PG_BACKEND = os.environ.get("TL_TEST_BACKEND") == "postgres"
PG_URL = os.environ.get("TL_TEST_PG_URL")
if PG_BACKEND and not PG_URL:
    raise pytest.UsageError("TL_TEST_BACKEND=postgres requires TL_TEST_PG_URL (a disposable test database)")
os.environ["TL_ENV"] = "dev"
os.environ["TL_DATABASE_URL"] = f"sqlite:///{_TMP / 'template.db'}"
os.environ["TL_CHECKPOINT_PATH"] = str(_TMP / "checkpoint-template.jsonl")
os.environ["TL_DEMO_PASSWORD"] = "Demo-Pass-2026!"
os.environ["TL_API_URL"] = "https://testserver/api"
os.environ["TL_DEVCERTS_DIR"] = str(_TMP / "devcerts")
os.environ["TL_OBJECT_DIR"] = str(_TMP / "objects")
os.environ["TL_SCANNER"] = "stub"
os.environ["TL_OBJECT_STORE"] = "fs"

from fastapi.testclient import TestClient  # noqa: E402

from app import invariants, models  # noqa: E402,F401
from app.config import get_settings  # noqa: E402
from app.db import Base, SessionLocal, make_engine, set_engine  # noqa: E402
from app.ledger import LEDGER  # noqa: E402
from app.main import create_app  # noqa: E402

PW = os.environ["TL_DEMO_PASSWORD"]


def pytest_addoption(parser):
    parser.addoption("--require-services", action="store_true", help="Fail if ClamAV, S3, Mailpit or PostgreSQL is missing")


@pytest.fixture(scope="session")
def service_config(request):
    from service_config import config
    required = request.config.getoption("--require-services") or os.environ.get("TL_REQUIRE_SERVICES") == "1"
    return lambda name: config(name, required)


@contextmanager
def pg_database(source="template0"):
    """Clone only a named test database and always remove our own clone, even on setup failure."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    url = make_url(PG_URL)
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    name = "tl_case_" + uuid.uuid4().hex
    assert source == "template0" or source.startswith("tl_case_")
    with admin.connect() as conn:
        # FILE_COPY avoids WAL-logging a full seeded database for every test clone.
        conn.execute(text(f'CREATE DATABASE "{name}" TEMPLATE "{source}" STRATEGY FILE_COPY'))
    try:
        yield url.set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture(scope="session")
def template_db():
    with ExitStack() as stack:
        template = stack.enter_context(pg_database()) if PG_BACKEND else _TMP / "template.db"
        eng = make_engine(template if PG_BACKEND else os.environ["TL_DATABASE_URL"])
        stack.callback(eng.dispose)
        Base.metadata.create_all(eng)
        with eng.begin() as c:
            invariants.install(c)
        set_engine(eng)
        from app.seed import seed_all
        with SessionLocal() as db:
            seed_all(db)
        eng.dispose()  # PostgreSQL cannot clone a database with pooled connections.
        yield template


@pytest.fixture()
def db_path(template_db, tmp_path) -> Path:
    from sqlalchemy.engine import make_url
    with ExitStack() as stack:
        p = tmp_path / "t.db"
        if PG_BACKEND:
            case_url = stack.enter_context(pg_database(make_url(template_db).database))
        else:
            shutil.copy(template_db, p)
            case_url = f"sqlite:///{p}"
            # Retain reports, not hundreds of disposable 4 MB database copies.
            def remove_case_db():
                for path in (p, Path(str(p) + "-wal"), Path(str(p) + "-shm")):
                    path.unlink(missing_ok=True)
            stack.callback(remove_case_db)
        shutil.copy(_TMP / "checkpoint-template.jsonl", tmp_path / "cp.jsonl")
        get_settings().checkpoint_path = str(tmp_path / "cp.jsonl")
        eng = make_engine(case_url)
        stack.callback(eng.dispose)
        set_engine(eng)
        LEDGER.k = None
        LEDGER.rebuild()
        from app.routers.auth import DEV_OTP_OUTBOX
        from app.ratelimit import reset
        DEV_OTP_OUTBOX.clear()
        reset()
        yield p


@pytest.fixture()
def app(db_path):
    return create_app(start_scheduler=False)


class Api:
    """A browser-like client: HTTPS (so Secure cookies flow), client header, CSRF header after login."""

    def __init__(self, app) -> None:
        self.c = TestClient(app, base_url="https://testserver")
        self.c.headers["X-TL-Client"] = "web"

    def login(self, username: str, role: str, method: str = "otp", password: str = PW):
        r = self.c.post("/api/auth/login", json={"username": username, "password": password, "role": role})
        assert r.status_code == 200, r.text
        if method == "otp":
            assert self.c.post("/api/auth/otp/send").status_code == 200
            code = self.c.get(f"/api/sim/otp-outbox/{username}").json()["code"]
            r = self.c.post("/api/auth/otp/verify", json={"code": code})
        elif method == "totp":
            code = self.c.get(f"/api/sim/totp/{username}").json()["code"]
            r = self.c.post("/api/auth/totp/verify", json={"code": code})
        assert r.status_code == 200, r.text
        self.c.headers["X-CSRF-Token"] = r.json()["user"]["csrf_token"]
        return self

    def __getattr__(self, name):
        return getattr(self.c, name)

    def dsc(self, username: str, message: str) -> dict:
        return self.c.post("/api/sim/dsc/sign", json={"username": username, "message": message}).json()


@pytest.fixture()
def api(app):
    return lambda: Api(app)


MEERA, KIRAN, RAVI, ANIL = "meera@aicte-india.org", "kiran@aicte-india.org", "ravi@aicte-india.org", "anil@aicte-india.org"
SHARMA, LEGAL, AUDITOR, ABC, XYZ = "sharma@aicte-india.org", "legal@aicte-india.org", "auditor@aicte-india.org", "1-12345678", "1-xyz-demo"
OFF, INS, AUD = "AICTE_OFFICIAL", "INSTITUTION", "AUDITOR"


def as_json(r):
    try:
        return r.json()
    except json.JSONDecodeError:
        return r.text
