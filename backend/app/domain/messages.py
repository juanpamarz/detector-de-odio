"""Contratos de mensajes que viajan por la cola (JSON serializable)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IncomingMessage(BaseModel):
    """Mensaje de grupo normalizado por el receptor antes de encolar."""

    update_id: int
    chat_id: int
    chat_title: str | None = None
    chat_type: str
    message_id: int
    user_id: int
    username: str | None = None
    first_name: str = "Usuario"
    last_name: str | None = None
    text: str = Field(max_length=8192)
    sent_at: datetime

    @property
    def display_name(self) -> str:
        return f"{self.first_name} (@{self.username})" if self.username else self.first_name


class IncomingCallback(BaseModel):
    """Pulsación de un botón en línea (retirar / publicar de todos modos)."""

    callback_id: str
    chat_id: int
    message_id: int
    from_user_id: int
    data: str


class MembershipChange(BaseModel):
    """El bot fue agregado, retirado, promovido o degradado en un grupo."""

    chat_id: int
    chat_title: str | None = None
    chat_type: str
    new_status: str
    can_delete_messages: bool | None = None
    can_restrict_members: bool | None = None


class GroupCommand(BaseModel):
    """Comando /registrar o /estado enviado en un grupo (llega aunque el modo privacidad esté activo)."""

    chat_id: int
    chat_title: str | None = None
    chat_type: str
    message_id: int
    command: str
    user_id: int
