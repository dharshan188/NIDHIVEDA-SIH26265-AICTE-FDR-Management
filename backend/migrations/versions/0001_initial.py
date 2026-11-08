"""Initial schema: ledger event stores, projections with money invariants, auth, bank simulator.

Revision ID: 0001
Revises:
Create Date: 2026-10-24
"""
from __future__ import annotations

from alembic import op

from app import invariants, models  # noqa: F401
from app.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # The ORM metadata is the single schema definition; this revision materialises it and
    # installs the dialect-specific invariant triggers. Later revisions use op.* diffs.
    Base.metadata.create_all(bind)
    invariants.install(bind)


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
