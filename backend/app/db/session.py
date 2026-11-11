"""Motor y fábrica de sesiones SQLAlchemy 2.x (síncrono, pool con pre-ping)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    if settings.serverless:
        # Serverless (Vercel + Neon): cada invocación abre y cierra su conexión; el pooler
        # de Neon (PgBouncer en modo transacción) no admite sentencias preparadas.
        return create_engine(settings.database_url, poolclass=NullPool,
                             connect_args={"prepare_threshold": None, "connect_timeout": 10})
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Unidad de trabajo transaccional para workers y CLI."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
