"""Herramientas de línea de comandos.

    python -m app.cli create-admin --email tu@correo.com --password '...' --name 'Juan Pablo'
    python -m app.cli import-sqlite --path /data/moderacion_bot.db
    python -m app.cli seed-demo --days 30
    python -m app.cli set-webhook          # usa PUBLIC_BASE_URL y TELEGRAM_WEBHOOK_SECRET
    python -m app.cli webhook-info
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.models import ActionTaken, DashboardUser, GroupMember, HourlyActivity, Incident, Role, UserResponse
from app.db.session import session_scope
from app.domain.categories import MACRO_OF, HateCategory
from app.services import repository as repo
from app.services.moderation import REDACTED

LEGACY_GROUP_ID = -1001000000001


def create_admin(email: str, password: str, name: str, role: str) -> None:
    with session_scope() as db:
        existing = db.scalar(select(DashboardUser).where(func.lower(DashboardUser.email) == email.lower()))
        if existing:
            existing.hashed_password = hash_password(password)
            existing.role = Role(role)
            existing.is_active = True
            print(f"Cuenta actualizada: {email}")
            return
        db.add(DashboardUser(email=email.lower(), full_name=name, hashed_password=hash_password(password),
                             role=Role(role), is_active=True))
    print(f"Cuenta creada: {email} ({role})")


def import_sqlite(path: str, tz_name: str) -> None:
    """Migra moderacion_bot.db (versión 1 del proyecto) al esquema normalizado."""
    tz = ZoneInfo(tz_name)
    src = sqlite3.connect(path)
    src.row_factory = sqlite3.Row
    rows = src.execute("SELECT * FROM registros_moderacion ORDER BY id").fetchall()
    imported = 0
    with session_scope() as db:
        first = datetime.now(tz=UTC)
        repo.upsert_group(db, LEGACY_GROUP_ID, "Grupo histórico (v1, SQLite)", "supergroup", first)
        for r in rows:
            at = datetime.strptime(r["fecha_hora"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz).astimezone(UTC)
            uid = int(r["usuario_id"] or 0) or 1
            repo.upsert_user(db, uid, None, r["usuario_nombre"] or "Anónimo", None)
            categoria = (r["categoria"] or "NORMAL").upper()
            flagged = categoria in {"TOXICO", "CRISIS"}
            repo.bump_hourly(db, LEGACY_GROUP_ID, at, flagged=int(flagged))
            if not flagged:
                continue
            crisis = categoria == "CRISIS"
            cat = HateCategory.SELF_HARM if crisis else HateCategory.INSULT
            db.execute(pg_insert(Incident).values(
                group_id=LEGACY_GROUP_ID, user_id=uid, telegram_message_id=-int(r["id"]),
                message_text=REDACTED if crisis else r["mensaje_texto"], is_text_redacted=crisis,
                category=cat, macro_category=MACRO_OF[cat], toxicity_score=0.0 if crisis else 0.8,
                crisis_score=0.9 if crisis else 0.0, category_scores={}, providers=[{"name": "legacy_v1"}],
                action=ActionTaken.DELETED_CRISIS_SUPPORT if crisis else ActionTaken.DELETED_WARNED,
                message_sent_at=at, created_at=at,
            ).on_conflict_do_nothing(constraint="uq_incidents_group_message"))
            imported += 1
    print(f"Importados {len(rows)} registros ({imported} incidentes) al grupo {LEGACY_GROUP_ID}.")


DEMO_GROUPS = [
    (-1002000000101, "Generación 2027 · Ciencia de Datos"),
    (-1002000000102, "Taller de Python — sabatino"),
    (-1002000000103, "Club de Robótica Facultad"),
    (-1002000000104, "Vecinos Juriquilla"),
    (-1002000000105, "Fútbol rápido los jueves"),
    (-1002000000106, "Intercambio de libros Qro"),
]
DEMO_TEXTS: dict[HateCategory, list[str]] = {
    HateCategory.INSULT: ["eres un inútil, nadie te soporta", "qué pendejo eres, en serio",
                          "cállate, no sabes nada", "das pena ajena cada que escribes"],
    HateCategory.HARASSMENT: ["nadie te quiere en este grupo, sálte ya", "otra vez tú? deja de escribir aquí",
                              "vamos a reportarte todos hasta que te vayas"],
    HateCategory.THREAT: ["a la salida te espero y vas a ver", "sé dónde vives, cuidado"],
    HateCategory.MISOGYNY: ["las mujeres no deberían opinar de programación", "vete a la cocina mejor"],
    HateCategory.XENOPHOBIA: ["regrésate a tu país", "los de fuera vienen a quitarnos todo"],
    HateCategory.RACISM: ["por tu color nunca vas a llegar a nada"],
    HateCategory.LGBTQ_PHOBIA: ["la gente como tú no debería estar en el equipo"],
    HateCategory.ABLEISM: ["escribes como si tuvieras retraso"],
    HateCategory.RELIGIOUS: ["tu religión es para ignorantes"],
    HateCategory.SEXUAL: ["mándame fotos tuyas por privado", "comentario sexual explícito no solicitado"],
}
CAT_WEIGHTS = {HateCategory.INSULT: 30, HateCategory.HARASSMENT: 16, HateCategory.THREAT: 7,
               HateCategory.MISOGYNY: 9, HateCategory.XENOPHOBIA: 5, HateCategory.RACISM: 4,
               HateCategory.LGBTQ_PHOBIA: 6, HateCategory.ABLEISM: 3, HateCategory.RELIGIOUS: 2,
               HateCategory.SEXUAL: 6, HateCategory.SELF_HARM: 3}
FIRST = ["Andrea", "Luis", "Mariana", "Diego", "Fernanda", "Jorge", "Valeria", "Emilio", "Ximena", "Santiago",
         "Renata", "Carlos", "Paola", "Iván", "Daniela", "Rodrigo", "Camila", "Héctor", "Sofía", "Óscar"]


def seed_demo(days: int, seed: int) -> None:
    """Datos sintéticos (claramente etiquetados) para presentar el panel."""
    rng = random.Random(seed)
    now = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
    users = [(7_000_000 + i, f"{rng.choice(FIRST).lower()}_{rng.randint(10, 99)}", rng.choice(FIRST))
             for i in range(60)]
    offenders = rng.sample(users, 14)
    group_risk = {gid: r for (gid, _), r in zip(DEMO_GROUPS, [1.6, 0.7, 0.5, 1.2, 1.4, 0.3], strict=True)}
    cats = list(CAT_WEIGHTS)
    weights = list(CAT_WEIGHTS.values())
    hourly: dict[tuple[int, datetime], list[int]] = defaultdict(lambda: [0, 0])
    warnings: dict[tuple[int, int], int] = defaultdict(int)
    msg_id = 1
    with session_scope() as db:
        for gid, title in DEMO_GROUPS:
            repo.upsert_group(db, gid, title, "supergroup", now)
        for uid, uname, fname in users:
            repo.upsert_user(db, uid, uname, fname, None)
        db.flush()
        for h in range(days * 24):
            at = now - timedelta(hours=h)
            local_hour = (at.hour - 6) % 24
            activity = 0.15 + (1.0 if 19 <= local_hour <= 23 else 0.55 if 9 <= local_hour <= 18 else 0.1)
            trend = 1.0 + 0.6 * (1 - h / (days * 24))  # tendencia creciente reciente
            for gid, _ in DEMO_GROUPS:
                analyzed = int(rng.gauss(22, 6) * activity * trend * group_risk[gid] ** 0.3)
                if analyzed <= 0:
                    continue
                hourly[(gid, at)][0] += analyzed
                n_inc = sum(1 for _ in range(analyzed) if rng.random() < 0.012 * group_risk[gid])
                for _ in range(n_inc):
                    cat = rng.choices(cats, weights)[0]
                    uid, uname, _f = rng.choice(offenders) if rng.random() < 0.75 else rng.choice(users)
                    crisis = cat is HateCategory.SELF_HARM
                    ts = at + timedelta(minutes=rng.randint(0, 59))
                    tox = round(min(0.99, rng.betavariate(6, 2)), 3) if not crisis else round(rng.uniform(.05, .3), 3)
                    if not crisis:
                        warnings[(gid, uid)] += 1
                    banned = not crisis and warnings[(gid, uid)] == get_settings().max_warnings > 0
                    action = (ActionTaken.DELETED_CRISIS_SUPPORT if crisis else
                              ActionTaken.DELETED_BANNED if banned else ActionTaken.DELETED_WARNED)
                    response = None
                    if action is ActionTaken.DELETED_WARNED and rng.random() < 0.45:
                        response = UserResponse.WITHDRAWN if rng.random() < 0.7 else UserResponse.REPUBLISHED
                    db.add(Incident(
                        group_id=gid, user_id=uid, telegram_message_id=msg_id,
                        message_text=REDACTED if crisis else rng.choice(DEMO_TEXTS[cat]), is_text_redacted=crisis,
                        category=cat, macro_category=MACRO_OF[cat], toxicity_score=tox,
                        crisis_score=round(rng.uniform(.7, .98), 3) if crisis else round(rng.uniform(0, .05), 3),
                        category_scores={cat.value: tox}, action=action, user_response=response,
                        providers=[{"name": "demo"}], message_sent_at=ts, created_at=ts,
                    ))
                    msg_id += 1
                    hourly[(gid, at)][1] += 1
        for (gid, bucket), (analyzed, flagged) in hourly.items():
            db.execute(pg_insert(HourlyActivity).values(group_id=gid, bucket=bucket, analyzed=analyzed,
                                                        flagged=flagged).on_conflict_do_nothing())
        max_w = get_settings().max_warnings
        for (gid, uid), count in warnings.items():
            db.execute(pg_insert(GroupMember).values(
                group_id=gid, user_id=uid, warnings=count, is_banned=0 < max_w <= count,
                banned_at=now if 0 < max_w <= count else None).on_conflict_do_nothing())
    print(f"Datos demo: {len(DEMO_GROUPS)} grupos, {msg_id - 1} incidentes en {days} días.")


def _bot_api(method: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    token = get_settings().telegram_bot_token
    if token is None:
        sys.exit("Falta TELEGRAM_BOT_TOKEN")
    r = httpx.post(f"https://api.telegram.org/bot{token.get_secret_value()}/{method}", json=payload or {}, timeout=20)
    return dict(r.json())


def set_webhook() -> None:
    s = get_settings()
    if not s.public_base_url or not s.telegram_webhook_secret:
        sys.exit("Define PUBLIC_BASE_URL y TELEGRAM_WEBHOOK_SECRET")
    url = s.public_base_url.rstrip("/") + "/api/telegram/webhook"
    print(json.dumps(_bot_api("setWebhook", {
        "url": url, "secret_token": s.telegram_webhook_secret.get_secret_value(),
        "allowed_updates": ["message", "edited_message", "callback_query", "my_chat_member"],
        "max_connections": 40, "drop_pending_updates": False,
    }), indent=2, ensure_ascii=False))


def main() -> None:
    configure_logging("WARNING")
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create-admin")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--name", default="Administrador")
    p.add_argument("--role", default="admin", choices=[r.value for r in Role])
    p = sub.add_parser("import-sqlite")
    p.add_argument("--path", required=True)
    p.add_argument("--tz", default="America/Mexico_City")
    p = sub.add_parser("seed-demo")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--seed", type=int, default=7)
    sub.add_parser("set-webhook")
    sub.add_parser("delete-webhook")
    sub.add_parser("webhook-info")
    args = parser.parse_args()

    if args.cmd == "create-admin":
        create_admin(args.email, args.password, args.name, args.role)
    elif args.cmd == "import-sqlite":
        import_sqlite(args.path, args.tz)
    elif args.cmd == "seed-demo":
        seed_demo(args.days, args.seed)
    elif args.cmd == "set-webhook":
        set_webhook()
    elif args.cmd == "delete-webhook":
        print(_bot_api("deleteWebhook"))
    elif args.cmd == "webhook-info":
        print(json.dumps(_bot_api("getWebhookInfo"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
