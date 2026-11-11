from __future__ import annotations

from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUser, DbSession
from app.api.schemas import CategorySlice, HeatCell, Overview, StackedRow, TimePoint
from app.services import analytics
from app.services.analytics import Scope

router = APIRouter(prefix="/analytics", tags=["analytics"])


def scope_dep(
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    group_id: int | None = None,
    tz: str = "America/Mexico_City",
) -> Scope:
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Zona horaria inválida") from None
    return Scope.last_days(days, group_id, tz)


ScopeDep = Annotated[Scope, Depends(scope_dep)]


@router.get("/overview", response_model=Overview)
def overview(_: CurrentUser, db: DbSession, scope: ScopeDep) -> Overview:
    return analytics.overview(db, scope)


@router.get("/distribution", response_model=list[CategorySlice])
def distribution(_: CurrentUser, db: DbSession, scope: ScopeDep) -> list[CategorySlice]:
    return analytics.distribution(db, scope)


@router.get("/timeseries", response_model=list[TimePoint])
def timeseries(_: CurrentUser, db: DbSession, scope: ScopeDep,
               granularity: Literal["hour", "day"] = "day") -> list[TimePoint]:
    if granularity == "hour" and (scope.until - scope.since).days > 14:
        raise HTTPException(422, "La granularidad por hora admite como máximo 14 días")
    return analytics.timeseries(db, scope, granularity)


@router.get("/top-users", response_model=list[StackedRow])
def top_users(_: CurrentUser, db: DbSession, scope: ScopeDep,
              limit: Annotated[int, Query(ge=3, le=25)] = 10) -> list[StackedRow]:
    return analytics.top_users(db, scope, limit)


@router.get("/groups-ranking", response_model=list[StackedRow])
def groups_ranking(_: CurrentUser, db: DbSession, scope: ScopeDep,
                   limit: Annotated[int, Query(ge=3, le=25)] = 10) -> list[StackedRow]:
    return analytics.group_ranking(db, scope, limit)


@router.get("/heatmap", response_model=list[HeatCell])
def heatmap(_: CurrentUser, db: DbSession, scope: ScopeDep) -> list[HeatCell]:
    return analytics.heatmap(db, scope)
