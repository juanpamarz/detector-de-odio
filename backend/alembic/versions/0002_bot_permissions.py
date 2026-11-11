"""Estado y permisos del bot por grupo

Revision ID: 0002_bot_permissions
Revises: 0001_initial
Create Date: 2026-11-10
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_bot_permissions"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("telegram_groups", sa.Column("bot_status", sa.String(20)))
    op.add_column("telegram_groups", sa.Column("can_delete", sa.Boolean()))
    op.add_column("telegram_groups", sa.Column("can_restrict", sa.Boolean()))
    op.add_column("telegram_groups", sa.Column("member_count", sa.Integer()))
    op.add_column("telegram_groups", sa.Column("checked_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    for col in ("checked_at", "member_count", "can_restrict", "can_delete", "bot_status"):
        op.drop_column("telegram_groups", col)
