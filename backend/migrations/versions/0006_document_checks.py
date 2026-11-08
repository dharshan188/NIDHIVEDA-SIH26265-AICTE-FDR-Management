"""Document content-check results and the last SHA-256 re-check on fdr_documents.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

COLS = [
    sa.Column("content_checks", sa.JSON),
    sa.Column("integrity_status", sa.String(40)),
    sa.Column("integrity_checked_at", sa.String(32)),
]


def upgrade() -> None:
    # 0001 materialises the current ORM metadata, so on a fresh database these columns may already exist
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("fdr_documents")}
    with op.batch_alter_table("fdr_documents") as b:
        for c in COLS:
            if c.name not in have:
                b.add_column(c)


def downgrade() -> None:
    with op.batch_alter_table("fdr_documents") as b:
        for c in COLS:
            b.drop_column(c.name)
