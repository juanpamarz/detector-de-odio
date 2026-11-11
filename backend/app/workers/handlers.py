"""Punto único de ejecución de tareas, compartido por Celery y por el endpoint HTTP de QStash."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.domain.messages import GroupCommand, IncomingCallback, IncomingMessage, MembershipChange
from app.nlp.engine import ModerationEngine, build_engine
from app.services.accounts import prepare
from app.services.moderation import ModerationService


@lru_cache
def get_engine_instance() -> ModerationEngine:
    return build_engine(get_settings())


@lru_cache
def get_service() -> ModerationService:
    return ModerationService(get_engine_instance(), get_settings())


async def run_task(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    prepare()
    service = get_service()
    if name == "process_message":
        return await service.handle_message(IncomingMessage.model_validate(payload))
    if name == "process_callback":
        return await service.handle_callback(IncomingCallback.model_validate(payload))
    if name == "membership_changed":
        return service.handle_membership(MembershipChange.model_validate(payload))
    if name == "group_command":
        return await service.handle_group_command(GroupCommand.model_validate(payload))
    if name == "private_start":
        await service.handle_private_start(int(payload["chat_id"]), str(payload.get("first_name", "")))
        return {"status": "sent"}
    raise ValueError(f"Tarea desconocida: {name}")
