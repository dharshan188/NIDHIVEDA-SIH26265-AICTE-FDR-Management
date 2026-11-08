"""Push notification devices for the mobile app.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001 materialises the whole ORM metadata, so a fresh database already has this table.
    if "push_devices" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "push_devices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String(400), nullable=False, unique=True),
        sa.Column("platform", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("last_seen", sa.DateTime, nullable=False),
    )
    op.create_index("ix_push_devices_user_id", "push_devices", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_push_devices_user_id", "push_devices")
    op.drop_table("push_devices")
