"""PII encryption: institution PAN and registered mobile (encrypted), simulator accounts keyed by blind index.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-24

Existing plaintext values are not converted here; run `scripts/encrypt_pii.py` once after upgrading.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    have = _cols("institutions")
    with op.batch_alter_table("institutions") as b:
        for name in ("pan", "registered_mobile"):
            if name not in have:
                b.add_column(sa.Column(name, sa.Text))
    have = _cols("sim_bank_accounts")
    with op.batch_alter_table("sim_bank_accounts") as b:
        if "account_enc" not in have:
            b.add_column(sa.Column("account_enc", sa.Text))
        b.alter_column("account", type_=sa.String(64))


def downgrade() -> None:
    with op.batch_alter_table("sim_bank_accounts") as b:
        b.drop_column("account_enc")
    with op.batch_alter_table("institutions") as b:
        b.drop_column("registered_mobile")
        b.drop_column("pan")
