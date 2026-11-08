"""Nudge Ladder (outbox columns, deliveries, preferences, action links, provider simulator, policy versions, scheduler
runs), user contact/login columns, scrutiny observations and field changes.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app import models  # noqa: F401
from app.db import Base

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

NEW_TABLES = ["notification_deliveries", "notification_prefs", "action_tokens", "provider_sim_messages", "notify_policy_versions",
              "scheduler_runs", "observations", "observation_replies", "field_changes"]
NOTIFICATION_COLS = [
    sa.Column("key", sa.String(120)), sa.Column("rung", sa.String(10), nullable=False, server_default="action"),
    sa.Column("template", sa.String(40)), sa.Column("params", sa.JSON), sa.Column("text_hi", sa.Text), sa.Column("window", sa.String(10)),
    sa.Column("institution_id", sa.String(16)), sa.Column("planned_at", sa.String(32)), sa.Column("ack_at", sa.String(32)),
    sa.Column("ack_by", sa.String(120)), sa.Column("ack_via", sa.String(10)),
    sa.Column("escalation_step", sa.Integer, nullable=False, server_default="0"),
    sa.Column("parent_id", sa.Integer), sa.Column("escalated_at", sa.String(32)),
]
USER_COLS = [sa.Column("mobile", sa.Text), sa.Column("lang", sa.String(2), nullable=False, server_default="en"),
             sa.Column("last_login_at", sa.DateTime), sa.Column("prev_login_at", sa.DateTime)]


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    have = _cols("notifications")
    with op.batch_alter_table("notifications") as b:
        for c in NOTIFICATION_COLS:
            if c.name not in have:
                b.add_column(c)
        if "key" not in have:
            b.create_unique_constraint("uq_notifications_key", ["key"])
    have = _cols("users")
    with op.batch_alter_table("users") as b:
        for c in USER_COLS:
            if c.name not in have:
                b.add_column(c)
    for t in NEW_TABLES:
        Base.metadata.tables[t].create(bind, checkfirst=True)
    # notices that existed before the Nudge Ladder were already shown in-app; the worker must not send them again
    op.execute("UPDATE notifications SET planned_at = at WHERE planned_at IS NULL")
    for name, cols in (("ix_notifications_planned_at", ["planned_at"]), ("ix_notifications_institution_id", ["institution_id"])):
        if name not in {i["name"] for i in sa.inspect(bind).get_indexes("notifications")}:
            op.create_index(name, "notifications", cols)


def downgrade() -> None:
    for t in reversed(NEW_TABLES):
        op.drop_table(t)
    with op.batch_alter_table("users") as b:
        for c in USER_COLS:
            b.drop_column(c.name)
    with op.batch_alter_table("notifications") as b:
        for c in NOTIFICATION_COLS:
            b.drop_column(c.name)
