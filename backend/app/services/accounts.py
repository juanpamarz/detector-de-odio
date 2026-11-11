"""Preparación perezosa: migraciones automáticas (AUTO_MIGRATE) y primer administrador."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import DashboardUser, Role
from app.db.session import get_engine, session_scope

logger = logging.getLogger(__name__)
_done = False
_schema_ready = False
ROOT = Path(__file__).resolve().parents[2]


def ensure_schema() -> None:
    """Aplica las migraciones pendientes (alembic upgrade head) si AUTO_MIGRATE=true.

    Pensado para serverless, donde no hay un paso de despliegue donde correr Alembic.
    Un candado consultivo *de transacción* evita que dos instancias migren a la vez; se
    libera solo al terminar la transacción, así funciona también detrás del pooler de Neon
    (PgBouncer en modo transacción), donde un candado de sesión podría quedar tomado.
    """
    global _schema_ready
    if _schema_ready or not get_settings().auto_migrate:
        return
    from alembic import command  # noqa: PLC0415
    from alembic.config import Config  # noqa: PLC0415

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    with get_engine().connect() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(746101)"))
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
        conn.commit()  # aplica las migraciones y libera el candado
    _schema_ready = True
    logger.info("schema_ready")


def prepare() -> None:
    ensure_schema()
    bootstrap_admin()


def bootstrap_admin() -> None:
    """Crea el primer administrador si no hay usuarios. Idempotente y barato tras la primera vez.

    Se llama al arrancar la API y también antes de cada login, porque en serverless
    (Vercel) los eventos de arranque no siempre se ejecutan.
    """
    global _done
    s = get_settings()
    if _done or not (s.first_admin_email and s.first_admin_password):
        return
    with session_scope() as db:
        if db.scalar(select(DashboardUser.id).limit(1)) is None:
            db.add(DashboardUser(email=s.first_admin_email.lower(), full_name=s.first_admin_name,
                                 hashed_password=hash_password(s.first_admin_password.get_secret_value()),
                                 role=Role.ADMIN, is_active=True))
            logger.info("admin_bootstrapped", extra={"email": s.first_admin_email})
    _done = True
