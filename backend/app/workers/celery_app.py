"""Aplicación Celery. Broker: RabbitMQ (docker compose o una VM).

Colas
-----
moderation    mensajes a clasificar (escala con KEDA según longitud de la cola)
interactions  botones, altas/bajas del bot, /start (baja latencia, poco volumen)
"""

from __future__ import annotations

from typing import Any

from celery import Celery
from celery.signals import setup_logging, worker_process_init

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()

celery_app = Celery("centinela", broker=settings.broker_url, include=["app.workers.tasks"])
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_backend=None,
    task_ignore_result=True,
    task_acks_late=True,  # si el worker muere a mitad, el mensaje vuelve a la cola
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # reparto justo entre nodos
    task_default_queue="moderation",
    task_time_limit=120,
    task_soft_time_limit=90,
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
    broker_transport_options={"visibility_timeout": 300},  # usado solo con Redis
)


@setup_logging.connect
def _configure_logging(**_: Any) -> None:
    configure_logging(settings.log_level)


@worker_process_init.connect
def _reset_db_pool(**_: Any) -> None:
    # Cada proceso hijo del prefork necesita su propio pool de conexiones.
    from app.db.session import get_engine  # noqa: PLC0415

    get_engine().dispose(close=False)
