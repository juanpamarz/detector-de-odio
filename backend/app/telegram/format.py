"""Formato de menciones para los mensajes del bot (HTML de Telegram)."""

from __future__ import annotations

import html


def full_name(first_name: str | None, last_name: str | None = None) -> str:
    return " ".join(p for p in (first_name, last_name) if p) or "Usuario"


def mention_html(user_id: int, first_name: str | None, last_name: str | None, username: str | None) -> str:
    """«Juan Pablo (@jpmonroy)». Sin @usuario, el nombre se enlaza al perfil para que también
    le llegue la notificación."""
    name = html.escape(full_name(first_name, last_name))
    if username:
        return f"{name} (@{html.escape(username)})"
    return f'<a href="tg://user?id={int(user_id)}">{name}</a>'


def mention_plain(first_name: str | None, last_name: str | None, username: str | None) -> str:
    """Versión sin HTML para el panel y los reportes."""
    name = full_name(first_name, last_name)
    return f"{name} (@{username})" if username else name
