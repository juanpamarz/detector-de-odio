"""Normaliza un Update de Telegram y lo ENCOLA. Nunca llama a la API de NLP.

Lo comparten el webhook (FastAPI / Vercel) y el gateway de polling (local), de modo
que ambos caminos producen exactamente las mismas tareas en la cola.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.domain.messages import GroupCommand, IncomingCallback, IncomingMessage, MembershipChange
from app.workers.queue import get_queue

logger = logging.getLogger(__name__)

GROUP_TYPES = {"group", "supergroup"}
ALLOWED_UPDATES = ["message", "edited_message", "callback_query", "my_chat_member"]
# Comandos de grupo que registran el grupo y reportan permisos. Telegram los entrega
# incluso con el modo privacidad ACTIVADO, por eso sirven para diagnosticar.
GROUP_COMMANDS = {"/registrar", "/estado", "/centinela", "/start"}


def _command(text: str) -> str | None:
    if not text.startswith("/"):
        return None
    head = text.split()[0].split("@")[0].lower()
    return head if head in GROUP_COMMANDS else None


def route_update(update: dict[str, Any]) -> str:
    """Devuelve el tipo de evento encolado (o 'ignored')."""
    queue = get_queue()
    update_id = int(update.get("update_id", 0))
    message = update.get("message") or update.get("edited_message")

    if message:
        chat = message.get("chat", {})
        sender = message.get("from") or {}
        text = message.get("text") or message.get("caption")
        is_group = chat.get("type") in GROUP_TYPES

        if is_group and text and (cmd := _command(text)):
            command = GroupCommand(chat_id=chat["id"], chat_title=chat.get("title"), chat_type=chat["type"],
                                   message_id=message["message_id"], command=cmd, user_id=sender.get("id", 0))
            queue.enqueue("group_command", command.model_dump(mode="json"), dedup_key=str(update_id))
            return "group_command"

        if is_group and text and not sender.get("is_bot"):
            incoming = IncomingMessage(
                update_id=update_id,
                chat_id=chat["id"],
                chat_title=chat.get("title"),
                chat_type=chat["type"],
                message_id=message["message_id"],
                user_id=sender["id"],
                username=sender.get("username"),
                first_name=sender.get("first_name") or "Usuario",
                last_name=sender.get("last_name"),
                text=text[:8192],
                sent_at=datetime.fromtimestamp(message.get("date", 0), tz=UTC),
            )
            queue.enqueue("process_message", incoming.model_dump(mode="json"), dedup_key=str(update_id))
            return "message"

        if chat.get("type") == "private" and (text or "").startswith("/start"):
            queue.enqueue("private_start", {"chat_id": chat["id"], "first_name": sender.get("first_name") or ""},
                          dedup_key=str(update_id))
            return "private_start"
        return "ignored"

    callback = update.get("callback_query")
    if callback and str(callback.get("data", "")).startswith("rv:") and callback.get("message"):
        incoming_cb = IncomingCallback(
            callback_id=callback["id"],
            chat_id=callback["message"]["chat"]["id"],
            message_id=callback["message"]["message_id"],
            from_user_id=callback["from"]["id"],
            data=callback["data"],
        )
        queue.enqueue("process_callback", incoming_cb.model_dump(mode="json"), dedup_key=str(update_id))
        return "callback"

    member = update.get("my_chat_member")
    if member and member.get("chat", {}).get("type") in GROUP_TYPES:
        new = member.get("new_chat_member", {})
        change = MembershipChange(
            chat_id=member["chat"]["id"],
            chat_title=member["chat"].get("title"),
            chat_type=member["chat"]["type"],
            new_status=new.get("status", "member"),
            can_delete_messages=new.get("can_delete_messages"),
            can_restrict_members=new.get("can_restrict_members"),
        )
        queue.enqueue("membership_changed", change.model_dump(mode="json"), dedup_key=str(update_id))
        return "membership"

    return "ignored"
