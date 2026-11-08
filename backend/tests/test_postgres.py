"""PostgreSQL-only checks. Run with TL_TEST_PG_URL=postgresql+psycopg://user:pass@host:port/db (skipped otherwise).

Runs the real Alembic migration and the seed against PostgreSQL, then checks the invariant triggers,
including two concurrent transactions racing to allocate the same credit.
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

LAKH = 100_000 * 100


@pytest.fixture(scope="module")
def pg(service_config, tmp_path_factory):
    from alembic import command
    from alembic.config import Config

    from app.db import SessionLocal, make_engine, set_engine
    from app.ledger import LEDGER
    from conftest import ROOT
    pg_url = service_config("postgres")
    eng = make_engine(pg_url)
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["url"] = pg_url
    command.upgrade(cfg, "head")
    set_engine(eng)
    LEDGER.k = None
    from app.seed import seed_all
    from app import security
    # Seeding issues fresh simulated certificates. Do not overwrite the certificates
    # paired with the ordinary application fixture's users and stored serials.
    original_certs = security.DEVCERTS
    security.DEVCERTS = tmp_path_factory.mktemp("pg-devcerts")
    try:
        with SessionLocal() as db:
            out = seed_all(db)
        yield eng, out
    finally:
        security.DEVCERTS = original_certs
        eng.dispose()


def test_pg_migration_and_seed(pg):
    eng, out = pg
    from app import models as m
    from app.db import SessionLocal
    from alembic.config import Config
    assert out["fdrs"] == 821
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(m.Fdr)) == 821
        from alembic.script import ScriptDirectory
        root = Path(__file__).resolve().parents[1]
        cfg = Config(str(root / "alembic.ini"))
        cfg.set_main_option("script_location", str(root / "migrations"))
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == ScriptDirectory.from_config(cfg).get_current_head()


def test_pg_trigger_blocks_over_allocation(pg):
    eng, _ = pg
    with eng.begin() as c:
        c.execute(text("INSERT INTO obligations VALUES ('PG-O','INST0003','t','ONLINE',100000000000,NULL,false)"))
    with pytest.raises(Exception, match="exceed credit"):
        with eng.begin() as c:
            c.execute(text("INSERT INTO allocations VALUES ('PG-A','CR-UTR-LMN-2017-0507','PG-O',1,'x',true)"))


def test_pg_event_store_insert_only(pg):
    eng, _ = pg
    for stmt in ("UPDATE kernel_events SET actor='x' WHERE seq=1", "DELETE FROM kernel_events WHERE seq=1", "DELETE FROM portal_events WHERE seq=1"):
        with pytest.raises(Exception, match="insert-only"):
            with eng.begin() as c:
                c.execute(text(stmt))


def test_pg_concurrent_allocations_cannot_both_pass(pg):
    """Two transactions each allocate 30 L of a fresh 50 L credit at the same moment. The trigger's row locks
    serialise them, so exactly one commits."""
    eng, _ = pg
    with eng.begin() as c:
        c.execute(text("INSERT INTO bank_credits VALUES ('PG-C','PG-UTR',:a,'deposit','SBI','x','2026-01-01')"), {"a": 50 * LAKH})
        c.execute(text("INSERT INTO obligations VALUES ('PG-O1','INST0003','t','ONLINE',:a,NULL,false),('PG-O2','INST0003','t','ONLINE',:a,NULL,false)"),
                  {"a": 100 * LAKH})
    barrier = threading.Barrier(2)
    results: list[str] = []

    def worker(i: int) -> None:
        try:
            with eng.begin() as c:
                barrier.wait()
                c.execute(text("INSERT INTO allocations VALUES (:id,'PG-C',:o,:a,'x',true)"), {"id": f"PG-R{i}", "o": f"PG-O{i}", "a": 30 * LAKH})
                c.execute(text("SELECT pg_sleep(0.3)"))
            results.append("ok")
        except Exception as e:  # noqa: BLE001
            results.append("refused" if "exceed credit" in str(e) else f"other: {e}")

    ts = [threading.Thread(target=worker, args=(i,)) for i in (1, 2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sorted(results) == ["ok", "refused"], results
    with eng.connect() as c:
        assert c.scalar(text("SELECT SUM(amount_paise) FROM allocations WHERE credit_id='PG-C'")) == 30 * LAKH
