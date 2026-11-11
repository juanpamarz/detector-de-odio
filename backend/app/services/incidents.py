"""Búsqueda paginada de incidentes con filtros avanzados (compartida por la tabla y los exportes)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.schemas import IncidentOut, Page
from app.db.models import ActionTaken, Incident, TelegramUser
from app.domain.categories import HateCategory, MacroCategory

SortKey = Literal["-created_at", "created_at", "-toxicity_score", "toxicity_score"]


@dataclass(slots=True)
class IncidentFilters:
    group_id: int | None = None
    user_id: int | None = None
    categories: list[HateCategory] = field(default_factory=list)
    macros: list[MacroCategory] = field(default_factory=list)
    actions: list[ActionTaken] = field(default_factory=list)
    min_score: float | None = None
    max_score: float | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    q: str | None = None
    sort: SortKey = "-created_at"


def _apply(stmt: Select[tuple[Incident]], f: IncidentFilters) -> Select[tuple[Incident]]:
    if f.group_id is not None:
        stmt = stmt.where(Incident.group_id == f.group_id)
    if f.user_id is not None:
        stmt = stmt.where(Incident.user_id == f.user_id)
    if f.categories:
        stmt = stmt.where(Incident.category.in_(f.categories))
    if f.macros:
        stmt = stmt.where(Incident.macro_category.in_(f.macros))
    if f.actions:
        stmt = stmt.where(Incident.action.in_(f.actions))
    if f.min_score is not None:
        stmt = stmt.where(Incident.toxicity_score >= f.min_score)
    if f.max_score is not None:
        stmt = stmt.where(Incident.toxicity_score <= f.max_score)
    if f.date_from is not None:
        stmt = stmt.where(Incident.created_at >= f.date_from)
    if f.date_to is not None:
        stmt = stmt.where(Incident.created_at <= f.date_to)
    if f.q:
        like = f"%{f.q.strip()}%"
        stmt = stmt.join(TelegramUser, TelegramUser.id == Incident.user_id).where(or_(
            Incident.message_text.ilike(like), TelegramUser.username.ilike(like), TelegramUser.first_name.ilike(like)))
    return stmt


def _order(stmt: Select[tuple[Incident]], sort: SortKey) -> Select[tuple[Incident]]:
    col = Incident.toxicity_score if "toxicity" in sort else Incident.created_at
    return stmt.order_by(col.desc() if sort.startswith("-") else col.asc(), Incident.id.desc())


def to_out(i: Incident) -> IncidentOut:
    return IncidentOut(
        id=i.id, created_at=i.created_at, message_sent_at=i.message_sent_at, group_id=i.group_id,
        group_title=i.group.title, user_id=i.user_id, user_display=i.user.display_name,
        message_text=i.message_text, is_text_redacted=i.is_text_redacted, category=i.category,
        macro_category=i.macro_category, toxicity_score=i.toxicity_score, crisis_score=i.crisis_score,
        action=i.action, user_response=i.user_response, providers=list(i.providers or []),
    )


def search(db: Session, f: IncidentFilters, page: int, page_size: int) -> Page[IncidentOut]:
    base = _apply(select(Incident), f)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(
        _order(base, f.sort).options(joinedload(Incident.group), joinedload(Incident.user))
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return Page[IncidentOut](items=[to_out(r) for r in rows], total=total, page=page, page_size=page_size)


def export_rows(db: Session, f: IncidentFilters, limit: int = 20_000) -> list[IncidentOut]:
    rows = db.execute(
        _order(_apply(select(Incident), f), f.sort)
        .options(joinedload(Incident.group), joinedload(Incident.user)).limit(limit)
    ).scalars().all()
    return [to_out(r) for r in rows]
