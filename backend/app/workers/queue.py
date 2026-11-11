"""Cola de tareas intercambiable (principio de inversión de dependencias).

El receptor (webhook o gateway) solo conoce `TaskQueue.enqueue`; quién procese la
tarea depende de QUEUE_BACKEND:

celery  RabbitMQ/Redis + nodos Celery que corren 24/7 (docker compose, una VM).
qstash  Upstash QStash recibe la tarea y la EMPUJA por HTTPS a
        `{PUBLIC_BASE_URL}/api/internal/tasks/{tarea}`; cada entrega es una invocación
        serverless independiente (escala a cero y en paralelo, con reintentos y backoff
        exponencial gestionados por QStash). No hay ningún proceso encendido esperando.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Literal, Protocol

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

TaskName = Literal["process_message", "process_callback", "membership_changed", "private_start", "group_command"]
TASK_QUEUES: dict[str, str] = {
    "process_message": "moderation",
    "process_callback": "interactions",
    "membership_changed": "interactions",
    "private_start": "interactions",
    "group_command": "interactions",
}


class QueueError(Exception):
    """No se pudo encolar: el receptor devuelve 503 y Telegram reintenta la entrega."""


class TaskQueue(Protocol):
    def enqueue(self, task: TaskName, payload: dict[str, Any], *, dedup_key: str | None = None) -> None: ...


class CeleryQueue:
    def enqueue(self, task: TaskName, payload: dict[str, Any], *, dedup_key: str | None = None) -> None:
        from app.workers import tasks  # noqa: PLC0415  (Celery solo se importa en este modo)

        getattr(tasks, task).apply_async(args=[payload], queue=TASK_QUEUES[task])


class QStashQueue:
    def __init__(self, base_url: str, token: str, public_base_url: str, retries: int) -> None:
        self._publish = base_url.rstrip("/") + "/v2/publish/"
        self._headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                         "Upstash-Retries": str(retries)}
        self._target = public_base_url.rstrip("/") + "/api/internal/tasks/"

    def enqueue(self, task: TaskName, payload: dict[str, Any], *, dedup_key: str | None = None) -> None:
        headers = dict(self._headers)
        if dedup_key:
            # Si Telegram reenvía el mismo update, QStash no lo entrega dos veces.
            headers["Upstash-Deduplication-Id"] = f"{task}-{dedup_key}"
        try:
            r = httpx.post(self._publish + self._target + task, headers=headers, json=payload, timeout=8)
        except httpx.HTTPError as exc:
            raise QueueError(f"QStash no respondió: {type(exc).__name__}") from exc
        if r.status_code >= 300:
            raise QueueError(f"QStash rechazó la tarea ({r.status_code}): {r.text[:200]}")


@lru_cache
def get_queue() -> TaskQueue:
    s = get_settings()
    if s.queue_backend == "qstash":
        assert s.qstash_token is not None and s.public_base_url is not None
        return QStashQueue(s.qstash_url, s.qstash_token.get_secret_value(), s.public_base_url, s.qstash_retries)
    return CeleryQueue()
