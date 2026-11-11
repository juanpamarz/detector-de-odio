"""Receptor del webhook de Telegram: valida, ENCOLA y responde 200 de inmediato.

Telegram reintenta si no recibe respuesta en pocos segundos; por eso aquí no se
llama a ninguna API de NLP. En Vercel esta función tarda ~100 ms (lo que toma
publicar en QStash) y luego termina: no queda ningún proceso encendido.
"""

from __future__ import annotations

import hmac
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.telegram.dispatcher import route_update

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def webhook(
    request: Request,
    secret: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> dict[str, Any]:
    expected = get_settings().telegram_webhook_secret
    if expected is None or secret is None or not hmac.compare_digest(secret, expected.get_secret_value()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Firma de webhook inválida")
    update: dict[str, Any] = await request.json()
    try:
        kind = await run_in_threadpool(route_update, update)
    except Exception:
        # Si la cola no responde, devolvemos 503 para que Telegram reintente la entrega.
        logger.exception("enqueue_failed", extra={"update_id": update.get("update_id")})
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Cola no disponible") from None
    logger.info("update_enqueued", extra={"update_id": update.get("update_id"), "kind": kind})
    return {"ok": True}
