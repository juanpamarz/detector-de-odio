"""Esquema inicial normalizado

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-10
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "dashboard_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", TS),
        sa.PrimaryKeyConstraint("id", name="pk_dashboard_users"),
    )
    op.create_index("ix_dashboard_users_email", "dashboard_users", ["email"], unique=True)

    op.create_table(
        "telegram_groups",
        sa.Column("id", sa.BigInteger(), autoincrement=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("chat_type", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("toxicity_threshold", sa.Float()),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("last_activity_at", TS),
        sa.PrimaryKeyConstraint("id", name="pk_telegram_groups"),
    )

    op.create_table(
        "telegram_users",
        sa.Column("id", sa.BigInteger(), autoincrement=False),
        sa.Column("username", sa.String(64)),
        sa.Column("first_name", sa.String(128), nullable=False),
        sa.Column("last_name", sa.String(128)),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_telegram_users"),
    )

    op.create_table(
        "group_members",
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("warnings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("banned_at", TS),
        sa.Column("last_incident_at", TS),
        sa.ForeignKeyConstraint(["group_id"], ["telegram_groups.id"], ondelete="CASCADE",
                                name="fk_group_members_group_id_telegram_groups"),
        sa.ForeignKeyConstraint(["user_id"], ["telegram_users.id"], ondelete="CASCADE",
                                name="fk_group_members_user_id_telegram_users"),
        sa.PrimaryKeyConstraint("group_id", "user_id", name="pk_group_members"),
    )

    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("is_text_redacted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("macro_category", sa.String(32), nullable=False),
        sa.Column("toxicity_score", sa.Float(), nullable=False),
        sa.Column("crisis_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("category_scores", JSONB, nullable=False),
        sa.Column("providers", JSONB, nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("user_response", sa.String(32)),
        sa.Column("warning_message_id", sa.BigInteger()),
        sa.Column("message_sent_at", TS, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["group_id"], ["telegram_groups.id"], ondelete="CASCADE",
                                name="fk_incidents_group_id_telegram_groups"),
        sa.ForeignKeyConstraint(["user_id"], ["telegram_users.id"], ondelete="CASCADE",
                                name="fk_incidents_user_id_telegram_users"),
        sa.PrimaryKeyConstraint("id", name="pk_incidents"),
        sa.UniqueConstraint("group_id", "telegram_message_id", name="uq_incidents_group_message"),
    )
    op.create_index("ix_incidents_group_id", "incidents", ["group_id"])
    op.create_index("ix_incidents_user_id", "incidents", ["user_id"])
    op.create_index("ix_incidents_category", "incidents", ["category"])
    op.create_index("ix_incidents_macro_category", "incidents", ["macro_category"])
    op.create_index("ix_incidents_created_at", "incidents", ["created_at"])
    op.create_index("ix_incidents_group_created", "incidents", ["group_id", "created_at"])

    op.create_table(
        "hourly_activity",
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("bucket", TS, nullable=False),
        sa.Column("analyzed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("flagged", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["group_id"], ["telegram_groups.id"], ondelete="CASCADE",
                                name="fk_hourly_activity_group_id_telegram_groups"),
        sa.PrimaryKeyConstraint("group_id", "bucket", name="pk_hourly_activity"),
    )


def downgrade() -> None:
    op.drop_table("hourly_activity")
    op.drop_table("incidents")
    op.drop_table("group_members")
    op.drop_table("telegram_users")
    op.drop_table("telegram_groups")
    op.drop_table("dashboard_users")
