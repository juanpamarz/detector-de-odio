from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.api.deps import CurrentUser, DbSession
from app.api.schemas import IncidentOut, Page
from app.db.models import ActionTaken, TelegramGroup
from app.domain.categories import HateCategory, MacroCategory
from app.services import exports
from app.services import incidents as svc
from app.services.incidents import IncidentFilters, SortKey

router = APIRouter(tags=["incidents"])


def filters_dep(
    group_id: int | None = None,
    user_id: int | None = None,
    category: Annotated[list[HateCategory] | None, Query()] = None,
    macro: Annotated[list[MacroCategory] | None, Query()] = None,
    action: Annotated[list[ActionTaken] | None, Query()] = None,
    min_score: Annotated[float | None, Query(ge=0, le=1)] = None,
    max_score: Annotated[float | None, Query(ge=0, le=1)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: SortKey = "-created_at",
) -> IncidentFilters:
    return IncidentFilters(group_id=group_id, user_id=user_id, categories=category or [], macros=macro or [],
                           actions=action or [], min_score=min_score, max_score=max_score,
                           date_from=date_from, date_to=date_to, q=q, sort=sort)


Filters = Annotated[IncidentFilters, Depends(filters_dep)]


@router.get("/incidents", response_model=Page[IncidentOut])
def list_incidents(_: CurrentUser, db: DbSession, f: Filters,
                   page: Annotated[int, Query(ge=1)] = 1,
                   page_size: Annotated[int, Query(ge=5, le=100)] = 25) -> Page[IncidentOut]:
    return svc.search(db, f, page, page_size)


def _tz(tz: str) -> str:
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Zona horaria inválida") from None
    return tz


def _describe(db: DbSession, f: IncidentFilters) -> tuple[str, str]:
    parts: list[str] = []
    scope = "todos los grupos"
    if f.group_id is not None:
        g = db.get(TelegramGroup, f.group_id)
        scope = f"grupo «{g.title}»" if g else f"grupo {f.group_id}"
    if f.macros:
        parts.append("macrocategorías: " + ", ".join(m.value for m in f.macros))
    if f.categories:
        parts.append("categorías: " + ", ".join(c.value for c in f.categories))
    if f.min_score is not None or f.max_score is not None:
        parts.append(f"toxicidad {f.min_score or 0:.2f}–{f.max_score or 1:.2f}")
    if f.date_from or f.date_to:
        parts.append(f"periodo {f.date_from:%d/%m/%Y}" if f.date_from else "periodo desde el inicio")
    if f.q:
        parts.append(f"búsqueda «{f.q}»")
    return scope, ("Filtros: " + "; ".join(parts) + ".") if parts else "Sin filtros adicionales."


@router.get("/exports/incidents.csv")
def export_csv(_: CurrentUser, db: DbSession, f: Filters, tz: str = "America/Mexico_City") -> Response:
    data = exports.to_csv(svc.export_rows(db, f), _tz(tz))
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M")
    return Response(data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="incidentes-{stamp}.csv"'})


@router.get("/exports/incidents.pdf")
def export_pdf(_: CurrentUser, db: DbSession, f: Filters, tz: str = "America/Mexico_City") -> Response:
    scope, desc = _describe(db, f)
    data = exports.to_pdf(svc.export_rows(db, f, limit=5000), title=f"Reporte de incidentes — {scope}",
                          filters_desc=desc, tz_name=_tz(tz))
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M")
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="incidentes-{stamp}.pdf"'})
