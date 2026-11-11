"""Consultas agregadas para el panel (PostgreSQL)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import Select, distinct, extract, func, literal, select
from sqlalchemy.orm import Session

from app.api.schemas import CategorySlice, HeatCell, Overview, StackedRow, TimePoint
from app.db.models import GroupMember, HourlyActivity, Incident, TelegramGroup, TelegramUser, UserResponse
from app.domain.categories import MacroCategory

MACROS = (MacroCategory.IDENTITY, MacroCategory.AGGRESSION, MacroCategory.SEXUAL, MacroCategory.CRISIS)


@dataclass(frozen=True, slots=True)
class Scope:
    since: datetime
    until: datetime
    group_id: int | None = None
    tz: str = "America/Mexico_City"

    @classmethod
    def last_days(cls, days: int, group_id: int | None = None, tz: str = "America/Mexico_City") -> Scope:
        until = datetime.now(tz=UTC)
        return cls(since=until - timedelta(days=days), until=until, group_id=group_id, tz=tz)

    @property
    def previous(self) -> Scope:
        span = self.until - self.since
        return Scope(self.since - span, self.since, self.group_id, self.tz)


def _inc_where(scope: Scope) -> list[object]:
    conds: list[object] = [Incident.created_at >= scope.since, Incident.created_at < scope.until]
    if scope.group_id is not None:
        conds.append(Incident.group_id == scope.group_id)
    return conds


def _act_where(scope: Scope) -> list[object]:
    conds: list[object] = [HourlyActivity.bucket >= scope.since, HourlyActivity.bucket < scope.until]
    if scope.group_id is not None:
        conds.append(HourlyActivity.group_id == scope.group_id)
    return conds


def overview(db: Session, scope: Scope) -> Overview:
    w = _inc_where(scope)
    incidents = db.scalar(select(func.count(Incident.id)).where(*w)) or 0
    prev = db.scalar(select(func.count(Incident.id)).where(*_inc_where(scope.previous))) or 0
    crisis = db.scalar(select(func.count(Incident.id)).where(*w, Incident.macro_category == MacroCategory.CRISIS)) or 0
    sanctioned = db.scalar(select(func.count(distinct(Incident.user_id)))
                           .where(*w, Incident.macro_category != MacroCategory.CRISIS)) or 0
    mean_tox = db.scalar(select(func.avg(Incident.toxicity_score))
                         .where(*w, Incident.macro_category != MacroCategory.CRISIS)) or 0.0
    analyzed = db.scalar(select(func.coalesce(func.sum(HourlyActivity.analyzed), 0)).where(*_act_where(scope))) or 0
    banned_q = select(func.count()).select_from(GroupMember).where(GroupMember.is_banned.is_(True))
    if scope.group_id is not None:
        banned_q = banned_q.where(GroupMember.group_id == scope.group_id)
    banned = db.scalar(banned_q) or 0
    groups_q = select(func.count(distinct(HourlyActivity.group_id))).where(*_act_where(scope))
    active_groups = db.scalar(groups_q) or 0
    resp = dict(db.execute(select(Incident.user_response, func.count()).where(*w, Incident.user_response.isnot(None))
                           .group_by(Incident.user_response)).tuples().all())
    return Overview(
        analyzed=int(analyzed), incidents=incidents, incidents_prev=prev, crisis=crisis,
        users_sanctioned=sanctioned, users_banned=banned, active_groups=active_groups,
        incident_rate=(incidents / analyzed) if analyzed else 0.0, mean_toxicity=float(mean_tox),
        withdrawn=int(resp.get(UserResponse.WITHDRAWN, 0)), republished=int(resp.get(UserResponse.REPUBLISHED, 0)),
    )


def distribution(db: Session, scope: Scope) -> list[CategorySlice]:
    rows = db.execute(
        select(Incident.macro_category, Incident.category, func.count())
        .where(*_inc_where(scope)).group_by(Incident.macro_category, Incident.category)
        .order_by(func.count().desc())
    ).tuples().all()
    return [CategorySlice(macro=m, category=c, count=n) for m, c, n in rows]


def timeseries(db: Session, scope: Scope, granularity: Literal["hour", "day"]) -> list[TimePoint]:
    tz = ZoneInfo(scope.tz)
    local_inc = func.date_trunc(granularity, func.timezone(scope.tz, Incident.created_at))
    local_act = func.date_trunc(granularity, func.timezone(scope.tz, HourlyActivity.bucket))

    buckets: dict[datetime, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for bucket, macro, n in db.execute(
        select(local_inc, Incident.macro_category, func.count()).where(*_inc_where(scope))
        .group_by(local_inc, Incident.macro_category)
    ).tuples():
        buckets[bucket][str(macro)] += n
        buckets[bucket]["incidents"] += n
    for bucket, n in db.execute(
        select(local_act, func.sum(HourlyActivity.analyzed)).where(*_act_where(scope)).group_by(local_act)
    ).tuples():
        buckets[bucket]["analyzed"] += int(n or 0)

    # Rellenar huecos para que la serie sea continua.
    step = timedelta(hours=1) if granularity == "hour" else timedelta(days=1)
    start = scope.since.astimezone(tz).replace(tzinfo=None, minute=0, second=0, microsecond=0)
    if granularity == "day":
        start = start.replace(hour=0)
    end = scope.until.astimezone(tz).replace(tzinfo=None)
    points: list[TimePoint] = []
    cur = start
    while cur <= end:
        b = buckets.get(cur, {})
        points.append(TimePoint(
            bucket=cur.replace(tzinfo=tz), analyzed=b.get("analyzed", 0), incidents=b.get("incidents", 0),
            identity_hate=b.get(MacroCategory.IDENTITY.value, 0), aggression=b.get(MacroCategory.AGGRESSION.value, 0),
            sexual=b.get(MacroCategory.SEXUAL.value, 0), crisis=b.get(MacroCategory.CRISIS.value, 0),
        ))
        cur += step
    return points


def _pivot(rows: list[tuple[int, str, MacroCategory, int]]) -> dict[int, StackedRow]:
    out: dict[int, StackedRow] = {}
    for key, label, macro, n in rows:
        row = out.setdefault(key, StackedRow(id=key, label=label, identity_hate=0, aggression=0, sexual=0,
                                             crisis=0, total=0))
        if macro in MACROS:
            setattr(row, MacroCategory(macro).value, getattr(row, MacroCategory(macro).value) + n)
        row.total += n
    return out


def top_users(db: Session, scope: Scope, limit: int = 10) -> list[StackedRow]:
    # «Nombre (@usuario)»; sin @usuario, solo el nombre.
    display = TelegramUser.first_name.op("||")(
        func.coalesce(literal(" (@").op("||")(TelegramUser.username).op("||")(literal(")")), literal("")))
    rows = db.execute(
        select(Incident.user_id, display, Incident.macro_category, func.count())
        .join(TelegramUser, TelegramUser.id == Incident.user_id)
        .where(*_inc_where(scope), Incident.macro_category != MacroCategory.CRISIS)  # crisis no es sanción
        .group_by(Incident.user_id, display, Incident.macro_category)
    ).tuples().all()
    pivot = _pivot([(uid, str(label), macro, n) for uid, label, macro, n in rows])
    ranked = sorted(pivot.values(), key=lambda r: r.total, reverse=True)[:limit]
    if ranked:
        mq = select(GroupMember.user_id, func.sum(GroupMember.warnings), func.bool_or(GroupMember.is_banned)) \
            .where(GroupMember.user_id.in_([r.id for r in ranked]))
        if scope.group_id is not None:
            mq = mq.where(GroupMember.group_id == scope.group_id)
        for uid, warnings, banned in db.execute(mq.group_by(GroupMember.user_id)).tuples():
            pivot[uid].extra = {"warnings": int(warnings or 0), "banned": bool(banned)}
    return ranked


def group_ranking(db: Session, scope: Scope, limit: int = 10) -> list[StackedRow]:
    rows = db.execute(
        select(Incident.group_id, TelegramGroup.title, Incident.macro_category, func.count())
        .join(TelegramGroup, TelegramGroup.id == Incident.group_id)
        .where(*_inc_where(scope)).group_by(Incident.group_id, TelegramGroup.title, Incident.macro_category)
    ).tuples().all()
    pivot = _pivot([(gid, title, macro, n) for gid, title, macro, n in rows])
    analyzed = dict(db.execute(select(HourlyActivity.group_id, func.sum(HourlyActivity.analyzed))
                               .where(*_act_where(scope)).group_by(HourlyActivity.group_id)).tuples().all())
    for gid, row in pivot.items():
        total = int(analyzed.get(gid) or 0)
        row.extra = {"analyzed": total, "rate": (row.total / total) if total else None}
    return sorted(pivot.values(), key=lambda r: r.total, reverse=True)[:limit]


def heatmap(db: Session, scope: Scope) -> list[HeatCell]:
    local = func.timezone(scope.tz, Incident.created_at)
    dow = extract("isodow", local)
    hour = extract("hour", local)
    counts = {(int(d) - 1, int(h)): n for d, h, n in db.execute(
        select(dow, hour, func.count()).where(*_inc_where(scope)).group_by(dow, hour)).tuples()}
    return [HeatCell(weekday=d, hour=h, count=counts.get((d, h), 0)) for d in range(7) for h in range(24)]


def groups_summary(db: Session, scope: Scope) -> list[dict[str, object]]:
    inc = (select(Incident.group_id.label("gid"), func.count().label("incidents"),
                  func.count().filter(Incident.macro_category == MacroCategory.CRISIS).label("crisis"))
           .where(*_inc_where(Scope(scope.since, scope.until))).group_by(Incident.group_id).subquery())
    act = (select(HourlyActivity.group_id.label("gid"), func.sum(HourlyActivity.analyzed).label("analyzed"))
           .where(*_act_where(Scope(scope.since, scope.until))).group_by(HourlyActivity.group_id).subquery())
    ban = (select(GroupMember.group_id.label("gid"), func.count().label("banned"))
           .where(GroupMember.is_banned.is_(True)).group_by(GroupMember.group_id).subquery())
    q: Select[tuple[TelegramGroup, int, int, int, int]] = (
        select(TelegramGroup, func.coalesce(inc.c.incidents, 0), func.coalesce(inc.c.crisis, 0),
               func.coalesce(act.c.analyzed, 0), func.coalesce(ban.c.banned, 0))
        .outerjoin(inc, inc.c.gid == TelegramGroup.id)
        .outerjoin(act, act.c.gid == TelegramGroup.id)
        .outerjoin(ban, ban.c.gid == TelegramGroup.id)
        .order_by(func.coalesce(inc.c.incidents, 0).desc(), TelegramGroup.title)
    )
    if scope.group_id is not None:
        q = q.where(TelegramGroup.id == scope.group_id)
    result: list[dict[str, object]] = []
    for group, incidents, crisis, analyzed, banned in db.execute(q).tuples():
        result.append({"group": group, "incidents": int(incidents), "crisis": int(crisis),
                       "analyzed": int(analyzed), "banned": int(banned)})
    return result

