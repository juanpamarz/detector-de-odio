"""Diagnóstico del bot: en qué grupos está, con qué permisos y cómo recibe los mensajes.

Telegram NO ofrece un método para listar los grupos en los que está un bot. Un grupo
se conoce cuando llega algún evento desde él:
  * se agrega o promueve al bot (my_chat_member),
  * alguien escribe (requiere modo privacidad desactivado en BotFather),
  * alguien envía /registrar (llega incluso con el modo privacidad activado),
  * o un moderador lo registra desde el panel con su ID o @usuario.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import Settings
from app.db.session import session_scope
from app.services import repository as repo
from app.telegram.client import TelegramAPIError, TelegramClient
from app.telegram.dispatcher import ALLOWED_UPDATES

logger = logging.getLogger(__name__)


def telegram_client(settings: Settings, http: httpx.AsyncClient) -> TelegramClient:
    if settings.telegram_bot_token is None:
        raise RuntimeError("TELEGRAM_BOT_TOKEN no está configurado")
    return TelegramClient(settings.telegram_bot_token.get_secret_value(), http)


def save_permissions(chat_id: int, title: str | None, chat_type: str, status: str,
                     can_delete: bool | None, can_restrict: bool | None, member_count: int | None = None) -> None:
    now = datetime.now(tz=UTC)
    with session_scope() as s:
        group = repo.upsert_group(s, chat_id, title, chat_type, now)
        group.bot_status = status
        # Un creador/administrador sin la lista explícita de permisos los tiene todos.
        group.can_delete = can_delete if can_delete is not None else status == "creator"
        group.can_restrict = can_restrict if can_restrict is not None else status == "creator"
        group.is_active = status in {"administrator", "creator", "member"}
        if member_count is not None:
            group.member_count = member_count
        group.checked_at = now


async def refresh_group(tg: TelegramClient, chat: int | str) -> dict[str, Any]:
    """Consulta a Telegram el grupo y los permisos del bot, y los guarda."""
    info = await tg.get_chat(chat)
    if info.get("type") not in {"group", "supergroup"}:
        raise ValueError("Ese chat no es un grupo")
    chat_id = int(info["id"])
    try:
        me = await tg.get_chat_member(chat_id, tg.bot_id)
        status = str(me.get("status", "member"))
    except TelegramAPIError:
        me, status = {}, "left"
    try:
        count: int | None = await tg.get_member_count(chat_id)
    except TelegramAPIError:
        count = None
    save_permissions(chat_id, info.get("title"), info["type"], status,
                     me.get("can_delete_messages"), me.get("can_restrict_members"), count)
    return {"id": chat_id, "title": info.get("title"), "bot_status": status,
            "can_delete": me.get("can_delete_messages", status == "creator"),
            "can_restrict": me.get("can_restrict_members", status == "creator"), "member_count": count}


def describe(status: str, can_delete: bool | None, can_restrict: bool | None, privacy_off: bool) -> str:
    lines = ["Grupo registrado en el panel de Centinela."]
    if status not in {"administrator", "creator"}:
        lines.append("Falta: hazme administrador del grupo para poder retirar mensajes.")
    else:
        lines.append(f"Borrar mensajes: {'sí' if can_delete else 'NO, actívalo en mis permisos de administrador'}.")
        lines.append(f"Expulsar miembros: {'sí' if can_restrict else 'no (no podré expulsar reincidentes)'}.")
    if not privacy_off:
        lines.append("Modo privacidad ACTIVADO: no veo los mensajes normales. En @BotFather envía /setprivacy, "
                     "elige este bot, selecciona Disable y vuelve a agregarme al grupo.")
    else:
        lines.append("Puedo leer los mensajes del grupo.")
    return "\n".join(lines)


async def bot_status(settings: Settings, engine_status: list[dict[str, object]]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as http:
        tg = telegram_client(settings, http)
        me = await tg.get_me()
        hook = await tg.get_webhook_info()
    expected = (settings.public_base_url.rstrip("/") + "/api/telegram/webhook") if settings.public_base_url else None
    last_error = hook.get("last_error_message")
    return {
        "username": me.get("username"),
        "name": me.get("first_name"),
        "privacy_mode": not me.get("can_read_all_group_messages", False),
        "can_join_groups": me.get("can_join_groups", True),
        "mode": "webhook" if hook.get("url") else "polling",
        "queue_backend": settings.queue_backend,
        "webhook_url": hook.get("url") or None,
        "expected_webhook_url": expected,
        "pending_updates": hook.get("pending_update_count", 0),
        "last_error": last_error,
        "last_error_at": (datetime.fromtimestamp(hook["last_error_date"], tz=UTC).isoformat()
                          if hook.get("last_error_date") else None),
        "providers": engine_status,
    }


async def connect_webhook(settings: Settings) -> str:
    if not (settings.public_base_url and settings.telegram_webhook_secret):
        raise ValueError("Define PUBLIC_BASE_URL y TELEGRAM_WEBHOOK_SECRET en las variables de entorno")
    url = settings.public_base_url.rstrip("/") + "/api/telegram/webhook"
    async with httpx.AsyncClient(timeout=10) as http:
        await telegram_client(settings, http).set_webhook(
            url, settings.telegram_webhook_secret.get_secret_value(), ALLOWED_UPDATES)
    logger.info("webhook_connected", extra={"url": url})
    return url
