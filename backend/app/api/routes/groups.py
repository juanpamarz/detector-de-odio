from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentUser, DbSession, ModeratorUser
from app.api.routes.analytics import scope_dep
from app.api.schemas import GroupOut, GroupUpdate
from app.core.config import get_settings
from app.db.models import TelegramGroup
from app.services import analytics
from app.services.analytics import Scope

router = APIRouter(prefix="/groups", tags=["groups"])


def _to_out(row: dict[str, object]) -> GroupOut:
    g = row["group"]
    assert isinstance(g, TelegramGroup)
    analyzed = int(row["analyzed"])  # type: ignore[call-overload]
    incidents = int(row["incidents"])  # type: ignore[call-overload]
    return GroupOut(
        id=g.id, title=g.title, chat_type=g.chat_type, is_active=g.is_active,
        toxicity_threshold=g.toxicity_threshold,
        effective_threshold=g.toxicity_threshold if g.toxicity_threshold is not None
        else get_settings().toxicity_threshold,
        last_activity_at=g.last_activity_at, analyzed=analyzed, incidents=incidents,
        crisis=int(row["crisis"]), banned=int(row["banned"]),  # type: ignore[call-overload]
        incident_rate=(incidents / analyzed) if analyzed else 0.0,
        bot_status=g.bot_status, can_delete=g.can_delete, can_restrict=g.can_restrict,
        member_count=g.member_count, checked_at=g.checked_at,
    )


@router.get("", response_model=list[GroupOut])
def list_groups(_: CurrentUser, db: DbSession, scope: Annotated[Scope, Depends(scope_dep)]) -> list[GroupOut]:
    return [_to_out(r) for r in analytics.groups_summary(db, scope)]


@router.get("/{group_id}", response_model=GroupOut)
def get_group(group_id: int, _: CurrentUser, db: DbSession,
              scope: Annotated[Scope, Depends(scope_dep)]) -> GroupOut:
    rows = analytics.groups_summary(db, Scope(scope.since, scope.until, group_id, scope.tz))
    if not rows:
        raise HTTPException(404, "Grupo no encontrado")
    return _to_out(rows[0])


@router.patch("/{group_id}", response_model=GroupOut)
def update_group(group_id: int, body: GroupUpdate, _: ModeratorUser, db: DbSession) -> GroupOut:
    group = db.get(TelegramGroup, group_id)
    if group is None:
        raise HTTPException(404, "Grupo no encontrado")
    if body.clear_threshold:
        group.toxicity_threshold = None
    elif body.toxicity_threshold is not None:
        group.toxicity_threshold = body.toxicity_threshold
    if body.is_active is not None:
        group.is_active = body.is_active
    db.commit()
    rows = analytics.groups_summary(db, Scope.last_days(30, group_id))
    return _to_out(rows[0])
