from __future__ import annotations

import sys
from pathlib import Path

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402,F401  (registers tables)
from app.config import get_settings  # noqa: E402
from app.db import Base, make_engine  # noqa: E402

target_metadata = Base.metadata


def run_migrations_online() -> None:
    url = context.config.attributes.get("url") or get_settings().database_url
    connectable = make_engine(url)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=url.startswith("sqlite"))
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
