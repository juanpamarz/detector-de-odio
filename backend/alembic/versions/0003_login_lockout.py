"""Bloqueo temporal de cuentas tras intentos fallidos

Revision ID: 0003_login_lockout
Revises: 0002_bot_permissions
Create Date: 2026-11-10
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_login_lockout"
down_revision: str | None = "0002_bot_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dashboard_users", sa.Column("failed_logins", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("dashboard_users", sa.Column("locked_until", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("dashboard_users", "locked_until")
    op.drop_column("dashboard_users", "failed_logins")
