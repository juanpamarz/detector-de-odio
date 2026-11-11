"""Nodo trabajador HTTP para el modo serverless (QUEUE_BACKEND=qstash).

QStash entrega cada tarea con una firma JWT (cabecera `Upstash-Signature`) firmada
con las claves de firma del proyecto. Se verifica la firma y el hash del cuerpo
antes de ejecutar nada, así nadie más puede invocar a los workers.

Códigos de respuesta y reintentos:
  200  tarea terminada (o descartada por datos inválidos: reintentar no ayudaría)
  503  error transitorio (Telegram o la BD no respondieron): QStash reintenta con backoff
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any

import jwt
from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.telegram.client import TelegramTransientError
from app.workers.handlers import run_task
from app.workers.queue import TASK_QUEUES

router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)
logger = logging.getLogger(__name__)


class InvalidSignatureError(Exception):
    pass


def verify_qstash_signature(token: str, body: bytes, keys: list[str]) -> dict[str, Any]:
    claims: dict[str, Any] | None = None
    for key in keys:
        try:
            claims = jwt.decode(token, key, algorithms=["HS256"], issuer="Upstash", leeway=30,
                                options={"verify_aud": False})
            break
        except jwt.InvalidSignatureError:
            continue
        except jwt.PyJWTError as exc:
            raise InvalidSignatureError(str(exc)) from exc
    if claims is None:
        raise InvalidSignatureError("firma no válida con ninguna clave")
    digest = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip("=")
    if str(claims.get("body", "")).rstrip("=") != digest:
        raise InvalidSignatureError("el cuerpo no coincide con la firma")
    return claims


@router.post("/tasks/{name}")
async def run(name: str, request: Request,
              upstash_signature: str | None = Header(default=None)) -> dict[str, Any]:
    if name not in TASK_QUEUES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tarea desconocida")
    s = get_settings()
    keys = [k.get_secret_value() for k in (s.qstash_current_signing_key, s.qstash_next_signing_key) if k]
    if not keys:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Faltan QSTASH_*_SIGNING_KEY")
    body = await request.body()
    try:
        verify_qstash_signature(upstash_signature or "", body, keys)
    except InvalidSignatureError as exc:
        logger.warning("qstash_signature_rejected", extra={"task": name, "reason": str(exc)})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Firma inválida") from None

    try:
        result = await run_task(name, json.loads(body))
    except (TelegramTransientError, OperationalError, ConnectionError) as exc:
        logger.warning("task_retry", extra={"task": name, "error": str(exc)})
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Reintentar") from None
    except (ValidationError, ValueError, KeyError) as exc:
        logger.error("task_discarded", extra={"task": name, "error": str(exc)})
        return {"status": "discarded"}
    logger.info("task_done", extra={"task": name, "status": result.get("status")})
    return result
