"""Document security: type, envelope-encryption metadata and malware-scan result on fdr_documents.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

COLS = [
    sa.Column("doc_type", sa.String(30), nullable=False, server_default="other"),
    sa.Column("uploaded_by", sa.String(120)),
    sa.Column("object_key", sa.String(200)),
    sa.Column("store_name", sa.String(20)),
    sa.Column("enc_alg", sa.String(40)),
    sa.Column("kek_id", sa.String(40)),
    sa.Column("wrapped_dek", sa.Text),
    sa.Column("nonce", sa.String(40)),
    sa.Column("scan_status", sa.String(12), nullable=False, server_default="unscanned"),
    sa.Column("scan_engine", sa.String(80)),
    sa.Column("scanned_at", sa.String(32)),
]


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("fdr_documents")}
    with op.batch_alter_table("fdr_documents") as b:
        for c in COLS:
            if c.name not in have:
                b.add_column(c)


def downgrade() -> None:
    with op.batch_alter_table("fdr_documents") as b:
        for c in COLS:
            b.drop_column(c.name)
