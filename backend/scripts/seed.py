"""Create the schema (Alembic) and seed the demo data through the kernel.

    python scripts/seed.py            # migrate + seed (skips if already seeded)
    python scripts/seed.py --reset    # dev only: delete the SQLite file first
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from app.config import get_settings  # noqa: E402


def main() -> None:
    cfg = get_settings()
    if "--reset" in sys.argv:
        if not cfg.is_dev or not cfg.database_url.startswith("sqlite:///"):
            sys.exit("--reset only works for the dev SQLite database")
        db_file = Path(cfg.database_url.removeprefix("sqlite:///"))
        for f in (db_file, db_file.with_suffix(".db-wal"), db_file.with_suffix(".db-shm")):
            f.unlink(missing_ok=True)
        cp = Path(cfg.checkpoint_path).expanduser()
        cp.unlink(missing_ok=True)
    alembic_cfg = Config(str(ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(alembic_cfg, "head")
    from app.db import SessionLocal
    from app.seed import seed_all
    t = time.time()
    with SessionLocal() as db:
        out = seed_all(db)
    print(f"seed: {out} in {time.time() - t:.1f}s")


if __name__ == "__main__":
    main()
