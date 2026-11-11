"""Estado del bot, conexión del webhook y registro/verificación de grupos desde el panel."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DbSession, ModeratorUser
from app.core.config import get_settings
from app.db.models import TelegramGroup
from app.services import bot_admin
from app.telegram.client import TelegramAPIError
from app.workers.handlers import get_engine_instance

router = APIRouter(prefix="/bot", tags=["bot"])


class RegisterGroup(BaseModel):
    chat: str = Field(min_length=2, max_length=64, description="ID numérico (-100…) o @usuario del grupo público")


def _chat_ref(raw: str) -> int | str:
    raw = raw.strip()
    try:
        return int(raw)
    except ValueError:
        return raw if raw.startswith("@") else f"@{raw}"


@router.get("/status")
async def status(_: CurrentUser) -> dict[str, Any]:
    try:
        return await bot_admin.bot_status(get_settings(), get_engine_instance().status())
    except TelegramAPIError as exc:
        raise HTTPException(502, f"Telegram respondió: {exc.description}") from None
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from None
    except httpx.HTTPError:
        raise HTTPException(502, "No se pudo conectar con Telegram; intenta de nuevo.") from None


@router.post("/webhook")
async def connect_webhook(_: AdminUser) -> dict[str, str]:
    try:
        url = await bot_admin.connect_webhook(get_settings())
    except TelegramAPIError as exc:
        raise HTTPException(400, f"Telegram respondió: {exc.description}") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    return {"webhook_url": url}


@router.post("/groups")
async def register_group(body: RegisterGroup, _: ModeratorUser) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as http:
        tg = bot_admin.telegram_client(get_settings(), http)
        try:
            return await bot_admin.refresh_group(tg, _chat_ref(body.chat))
        except TelegramAPIError as exc:
            raise HTTPException(404, "Telegram no encontró ese grupo o el bot no pertenece a él. "
                                     "Agrega primero el bot al grupo.") from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None


@router.post("/groups/refresh")
async def refresh_all(_: ModeratorUser, db: DbSession) -> dict[str, Any]:
    # Excluye los grupos sintéticos (histórico v1 y datos demo), que no existen en Telegram.
    ids = list(db.scalars(select(TelegramGroup.id).where(TelegramGroup.id != -1001000000001)
                          .where(TelegramGroup.id.not_between(-1002000000199, -1002000000100))))
    ok, failed = 0, 0
    async with httpx.AsyncClient(timeout=15) as http:
        tg = bot_admin.telegram_client(get_settings(), http)
        for gid in ids:
            try:
                await bot_admin.refresh_group(tg, gid)
                ok += 1
            except (TelegramAPIError, ValueError):
                bot_admin.save_permissions(gid, None, "supergroup", "left", None, None)
                failed += 1
    return {"checked": ok, "unreachable": failed}


@router.post("/groups/{group_id}/refresh")
async def refresh_one(group_id: int, _: ModeratorUser) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as http:
        tg = bot_admin.telegram_client(get_settings(), http)
        try:
            return await bot_admin.refresh_group(tg, group_id)
        except TelegramAPIError as exc:
            bot_admin.save_permissions(group_id, None, "supergroup", "left", None, None)
            raise HTTPException(404, f"El bot ya no tiene acceso a este grupo: {exc.description}") from None
