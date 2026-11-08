from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(eng, "connect")
        def _pragmas(dbapi_conn, _):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        return eng
    return create_engine(url, pool_pre_ping=True)


_engine: Engine | None = None
_Session: sessionmaker | None = None


def engine() -> Engine:
    global _engine, _Session
    if _engine is None:
        _engine = make_engine(get_settings().database_url)
        _Session = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def set_engine(eng: Engine) -> None:
    """Used by tests to point the app at a throwaway database."""
    global _engine, _Session
    _engine = eng
    _Session = sessionmaker(eng, expire_on_commit=False)


def SessionLocal() -> Session:  # noqa: N802
    engine()
    assert _Session is not None
    return _Session()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
