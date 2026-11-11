"""Tareas Celery (modo QUEUE_BACKEND=celery). Delegan en `handlers.run_task`."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.exc import OperationalError

from app.telegram.client import TelegramTransientError
from app.workers.celery_app import celery_app
from app.workers.handlers import run_task

RETRYABLE = (TelegramTransientError, OperationalError, ConnectionError)


@celery_app.task(name="moderation.process_message", autoretry_for=RETRYABLE, retry_backoff=2,
                 retry_backoff_max=120, retry_jitter=True, max_retries=6)
def process_message(payload: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(run_task("process_message", payload))


@celery_app.task(name="interactions.process_callback", autoretry_for=RETRYABLE, retry_backoff=1,
                 retry_backoff_max=20, max_retries=3)
def process_callback(payload: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(run_task("process_callback", payload))


@celery_app.task(name="interactions.membership_changed", autoretry_for=RETRYABLE, retry_backoff=1, max_retries=5)
def membership_changed(payload: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(run_task("membership_changed", payload))


@celery_app.task(name="interactions.group_command", autoretry_for=RETRYABLE, retry_backoff=1, max_retries=3)
def group_command(payload: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(run_task("group_command", payload))


@celery_app.task(name="interactions.private_start", autoretry_for=RETRYABLE, retry_backoff=1, max_retries=3)
def private_start(payload: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(run_task("private_start", payload))
