"""Acceso a datos del dominio de Telegram (upserts atómicos con ON CONFLICT)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import GroupMember, HourlyActivity, Incident, TelegramGroup, TelegramUser


def hour_bucket(at: datetime) -> datetime:
    return at.replace(minute=0, second=0, microsecond=0)


def upsert_group(session: Session, chat_id: int, title: str | None, chat_type: str, at: datetime) -> TelegramGroup:
    stmt = pg_insert(TelegramGroup).values(
        id=chat_id, title=title or "Grupo sin título", chat_type=chat_type, is_active=True, last_activity_at=at,
    )
    update_cols = {"chat_type": stmt.excluded.chat_type, "last_activity_at": stmt.excluded.last_activity_at}
    if title:
        update_cols["title"] = stmt.excluded.title
    session.execute(stmt.on_conflict_do_update(index_elements=[TelegramGroup.id], set_=update_cols))
    group = session.get(TelegramGroup, chat_id, populate_existing=True)
    assert group is not None
    return group


def upsert_user(session: Session, user_id: int, username: str | None, first_name: str,
                last_name: str | None) -> None:
    stmt = pg_insert(TelegramUser).values(id=user_id, username=username, first_name=first_name, last_name=last_name)
    session.execute(stmt.on_conflict_do_update(
        index_elements=[TelegramUser.id],
        set_={"username": stmt.excluded.username, "first_name": stmt.excluded.first_name,
              "last_name": stmt.excluded.last_name},
    ))


def lock_member(session: Session, group_id: int, user_id: int) -> GroupMember:
    """Obtiene la membresía con bloqueo de fila (evita carreras entre workers)."""
    session.execute(pg_insert(GroupMember).values(group_id=group_id, user_id=user_id, warnings=0, is_banned=False)
                    .on_conflict_do_nothing(index_elements=[GroupMember.group_id, GroupMember.user_id]))
    member = session.execute(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id).with_for_update()
    ).scalar_one()
    return member


def bump_hourly(session: Session, group_id: int, at: datetime, *, analyzed: int = 1, flagged: int = 0) -> None:
    stmt = pg_insert(HourlyActivity).values(group_id=group_id, bucket=hour_bucket(at), analyzed=analyzed,
                                            flagged=flagged)
    session.execute(stmt.on_conflict_do_update(
        index_elements=[HourlyActivity.group_id, HourlyActivity.bucket],
        set_={"analyzed": HourlyActivity.analyzed + stmt.excluded.analyzed,
              "flagged": HourlyActivity.flagged + stmt.excluded.flagged},
    ))


def find_incident(session: Session, group_id: int, message_id: int) -> Incident | None:
    return session.execute(
        select(Incident).where(Incident.group_id == group_id, Incident.telegram_message_id == message_id)
    ).scalar_one_or_none()
