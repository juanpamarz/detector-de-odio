"""Esquema relacional normalizado (3FN).

    dashboard_users            usuarios del panel (JWT + roles)
    telegram_groups  1 ─┐
                        ├─< group_members >─┐
    telegram_users   1 ─┘                   │
                        └─────< incidents >─┘   (un incidente = un mensaje moderado)
    hourly_activity            contador (grupo, hora) de mensajes analizados / marcados

Los textos de crisis se guardan redactados por defecto (STORE_CRISIS_TEXT=false).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.categories import HateCategory, MacroCategory

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

JsonType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class Role(StrEnum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    ANALYST = "analyst"


class ActionTaken(StrEnum):
    DELETED_WARNED = "deleted_warned"
    DELETED_BANNED = "deleted_banned"
    DELETED_CRISIS_SUPPORT = "deleted_crisis_support"
    LOGGED_ONLY = "logged_only"


class UserResponse(StrEnum):
    WITHDRAWN = "withdrawn"
    REPUBLISHED = "republished"


def _enum(cls: type[StrEnum], name: str) -> Enum:
    return Enum(cls, name=name, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class DashboardUser(Base):
    __tablename__ = "dashboard_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(_enum(Role, "role"), default=Role.ANALYST)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TelegramGroup(Base):
    __tablename__ = "telegram_groups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(255), default="Grupo sin título")
    chat_type: Mapped[str] = mapped_column(String(20), default="supergroup")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    toxicity_threshold: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Estado del bot en el grupo (se actualiza con /registrar, al cambiar sus permisos o desde el panel)
    bot_status: Mapped[str | None] = mapped_column(String(20))  # administrator, member, left, kicked
    can_delete: Mapped[bool | None] = mapped_column(Boolean)
    can_restrict: Mapped[bool | None] = mapped_column(Boolean)
    member_count: Mapped[int | None] = mapped_column(Integer)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    incidents: Mapped[list[Incident]] = relationship(back_populates="group")


class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(128), default="Usuario")
    last_name: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def display_name(self) -> str:
        full = " ".join(p for p in (self.first_name, self.last_name) if p) or "Usuario"
        return f"{full} (@{self.username})" if self.username else full


class GroupMember(Base):
    __tablename__ = "group_members"

    group_id: Mapped[int] = mapped_column(ForeignKey("telegram_groups.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id", ondelete="CASCADE"), primary_key=True)
    warnings: Mapped[int] = mapped_column(Integer, default=0)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_incident_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("group_id", "telegram_message_id", name="uq_incidents_group_message"),
        Index("ix_incidents_group_created", "group_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("telegram_groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id", ondelete="CASCADE"), index=True)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger)
    message_text: Mapped[str] = mapped_column(Text)
    is_text_redacted: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[HateCategory] = mapped_column(_enum(HateCategory, "hate_category"), index=True)
    macro_category: Mapped[MacroCategory] = mapped_column(_enum(MacroCategory, "macro_category"), index=True)
    toxicity_score: Mapped[float] = mapped_column(Float)
    crisis_score: Mapped[float] = mapped_column(Float, default=0.0)
    category_scores: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    providers: Mapped[list[Any]] = mapped_column(JsonType, default=list)
    action: Mapped[ActionTaken] = mapped_column(_enum(ActionTaken, "action_taken"))
    user_response: Mapped[UserResponse | None] = mapped_column(_enum(UserResponse, "user_response"))
    warning_message_id: Mapped[int | None] = mapped_column(BigInteger)
    message_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    group: Mapped[TelegramGroup] = relationship(back_populates="incidents")
    user: Mapped[TelegramUser] = relationship()


class HourlyActivity(Base):
    __tablename__ = "hourly_activity"

    group_id: Mapped[int] = mapped_column(ForeignKey("telegram_groups.id", ondelete="CASCADE"), primary_key=True)
    bucket: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    analyzed: Mapped[int] = mapped_column(Integer, default=0)
    flagged: Mapped[int] = mapped_column(Integer, default=0)
