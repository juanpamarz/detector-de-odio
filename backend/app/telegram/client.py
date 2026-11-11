"""Cliente mínimo y asíncrono de la Telegram Bot API (solo los métodos que usamos).

Se usa httpx directamente para que los workers no carguen python-telegram-bot y
para controlar con precisión los reintentos (429 con `retry_after`, 5xx).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TelegramAPIError(Exception):
    def __init__(self, method: str, description: str, status: int | None = None) -> None:
        super().__init__(f"{method}: {description}")
        self.method = method
        self.description = description
        self.status = status


class TelegramTransientError(TelegramAPIError):
    """Error recuperable: Celery reintenta la tarea con backoff exponencial."""


class TelegramClient:
    def __init__(self, token: str, http: httpx.AsyncClient, *, max_attempts: int = 3) -> None:
        self._base = f"https://api.telegram.org/bot{token}"
        self._http = http
        self._max_attempts = max_attempts

    async def call(self, method: str, **params: Any) -> Any:
        payload = {k: v for k, v in params.items() if v is not None}
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._http.post(f"{self._base}/{method}", json=payload)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == self._max_attempts:
                    raise TelegramTransientError(method, type(exc).__name__) from exc
                await asyncio.sleep(2 ** attempt)
                continue
            body: dict[str, Any] = response.json() if response.content else {}
            if body.get("ok"):
                return body.get("result")
            description = str(body.get("description", response.text[:200]))
            if response.status_code == 429:
                retry_after = int((body.get("parameters") or {}).get("retry_after", 2 ** attempt))
                logger.warning("telegram_rate_limited", extra={"method": method, "retry_after": retry_after})
                if attempt < self._max_attempts and retry_after <= 30:
                    await asyncio.sleep(retry_after)
                    continue
                raise TelegramTransientError(method, description, 429)
            if response.status_code >= 500:
                if attempt < self._max_attempts:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise TelegramTransientError(method, description, response.status_code)
            raise TelegramAPIError(method, description, response.status_code)
        raise TelegramTransientError(method, "agotados los reintentos")

    # --- Acciones de moderación ------------------------------------------
    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        try:
            await self.call("deleteMessage", chat_id=chat_id, message_id=message_id)
            return True
        except TelegramTransientError:
            raise
        except TelegramAPIError as exc:
            # Ya borrado (reintento idempotente) o el bot no es administrador.
            logger.warning("telegram_delete_failed", extra={"chat_id": chat_id, "reason": exc.description})
            return False

    async def send_message(self, chat_id: int, text: str, *,
                           reply_markup: dict[str, Any] | None = None) -> int | None:
        result = await self.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML",
                                 reply_markup=reply_markup, disable_web_page_preview=True)
        return int(result["message_id"]) if isinstance(result, dict) else None

    async def ban_chat_member(self, chat_id: int, user_id: int) -> None:
        await self.call("banChatMember", chat_id=chat_id, user_id=user_id)

    async def edit_message_text(self, chat_id: int, message_id: int, text: str) -> None:
        await self.call("editMessageText", chat_id=chat_id, message_id=message_id, text=text, parse_mode="HTML")

    # --- Diagnóstico y administración ---------------------------------------
    @property
    def bot_id(self) -> int:
        return int(self._base.rsplit("/bot", 1)[1].split(":", 1)[0])

    async def get_me(self) -> dict[str, Any]:
        return dict(await self.call("getMe"))

    async def get_chat(self, chat_id: int | str) -> dict[str, Any]:
        return dict(await self.call("getChat", chat_id=chat_id))

    async def get_chat_member(self, chat_id: int | str, user_id: int) -> dict[str, Any]:
        return dict(await self.call("getChatMember", chat_id=chat_id, user_id=user_id))

    async def get_member_count(self, chat_id: int | str) -> int:
        return int(await self.call("getChatMemberCount", chat_id=chat_id))

    async def get_webhook_info(self) -> dict[str, Any]:
        return dict(await self.call("getWebhookInfo"))

    async def set_webhook(self, url: str, secret: str, allowed_updates: list[str]) -> None:
        await self.call("setWebhook", url=url, secret_token=secret, allowed_updates=allowed_updates,
                        max_connections=40)

    async def answer_callback(self, callback_id: str, text: str, *, alert: bool = False) -> None:
        await self.call("answerCallbackQuery", callback_query_id=callback_id, text=text, show_alert=alert)
