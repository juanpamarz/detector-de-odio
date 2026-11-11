"""Caso de uso principal: clasificar -> decidir -> actuar en Telegram -> registrar.

Garantías
---------
* Idempotencia: (group_id, telegram_message_id) es único; un reintento de Celery
  no duplica incidentes ni advertencias.
* El borrado ocurre ANTES de persistir, para que el contenido dañino desaparezca
  lo antes posible; las notificaciones posteriores son best-effort.
"""

from __future__ import annotations

import html
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.db.models import ActionTaken, Incident, TelegramUser, UserResponse
from app.db.session import session_scope
from app.domain.categories import MACRO_OF, HateCategory
from app.domain.messages import GroupCommand, IncomingCallback, IncomingMessage, MembershipChange
from app.nlp.base import ModerationDecision
from app.nlp.engine import ModerationEngine
from app.services import bot_admin
from app.services import repository as repo
from app.services.policy import Thresholds, Verdict, build_thresholds, can_republish, decide
from app.telegram.format import mention_html
from app.telegram.client import TelegramAPIError, TelegramClient, TelegramTransientError

logger = logging.getLogger(__name__)
REDACTED = "[contenido protegido: posible crisis personal]"


class ModerationService:
    def __init__(self, engine: ModerationEngine, settings: Settings) -> None:
        self._engine = engine
        self._settings = settings

    def _telegram(self, http: httpx.AsyncClient) -> TelegramClient:
        token = self._settings.telegram_bot_token
        if token is None:
            raise RuntimeError("TELEGRAM_BOT_TOKEN no configurado")
        return TelegramClient(token.get_secret_value(), http)

    def _thresholds(self, group_override: float | None) -> Thresholds:
        return build_thresholds(self._settings, group_override)

    # ------------------------------------------------------------------ mensajes
    async def handle_message(self, msg: IncomingMessage) -> dict[str, Any]:
        now = datetime.now(tz=UTC)
        with session_scope() as s:
            group = repo.upsert_group(s, msg.chat_id, msg.chat_title, msg.chat_type, now)
            repo.upsert_user(s, msg.user_id, msg.username, msg.first_name, msg.last_name)
            override, active = group.toxicity_threshold, group.is_active
            if repo.find_incident(s, msg.chat_id, msg.message_id):
                return {"status": "duplicate"}
        if not active:
            return {"status": "group_paused"}

        async with httpx.AsyncClient(timeout=self._settings.nlp_timeout_seconds) as http:
            decision = await self._engine.classify(msg.text, http)
            thresholds = self._thresholds(override)
            verdict = decide(decision, thresholds)
            log_ctx = {"chat_id": msg.chat_id, "message_id": msg.message_id, "verdict": verdict.value,
                       "toxicity": decision.toxicity, "crisis": decision.crisis, "category": decision.category.value}
            logger.info("message_classified", extra=log_ctx)

            if verdict is Verdict.ALLOW:
                with session_scope() as s:
                    repo.bump_hourly(s, msg.chat_id, now)
                return {"status": "allowed", **log_ctx}

            tg = self._telegram(http)
            if verdict is Verdict.CRISIS_SUPPORT:
                return await self._handle_crisis(tg, msg, decision, now)
            return await self._handle_toxic(tg, msg, decision, thresholds, now)

    def _new_incident(self, msg: IncomingMessage, decision: ModerationDecision, action: ActionTaken,
                      *, crisis: bool) -> Incident:
        category = HateCategory.SELF_HARM if crisis else decision.category
        if category is HateCategory.NONE:
            category = HateCategory.INSULT
        redact = crisis and not self._settings.store_crisis_text
        return Incident(
            group_id=msg.chat_id, user_id=msg.user_id, telegram_message_id=msg.message_id,
            message_text=REDACTED if redact else msg.text, is_text_redacted=redact,
            category=category, macro_category=MACRO_OF[category],
            toxicity_score=decision.toxicity, crisis_score=decision.crisis,
            category_scores={c.value: v for c, v in decision.category_scores.items()},
            providers=decision.providers_summary(), action=action, message_sent_at=msg.sent_at,
        )

    async def _handle_crisis(self, tg: TelegramClient, msg: IncomingMessage, decision: ModerationDecision,
                             now: datetime) -> dict[str, Any]:
        deleted = await tg.delete_message(msg.chat_id, msg.message_id)
        try:
            with session_scope() as s:
                action = ActionTaken.DELETED_CRISIS_SUPPORT if deleted else ActionTaken.LOGGED_ONLY
                s.add(self._new_incident(msg, decision, action, crisis=True))
                repo.bump_hourly(s, msg.chat_id, now, flagged=1)
        except IntegrityError:
            return {"status": "duplicate"}

        name = html.escape(msg.first_name)
        try:
            await tg.send_message(msg.user_id, html.escape(self._settings.crisis_support_message.format(name=name)))
        except TelegramAPIError:
            # El usuario nunca abrió chat privado con el bot: aviso discreto en el grupo.
            await self._safe_send(tg, msg.chat_id,
                                  f"{mention_html(msg.user_id, msg.first_name, msg.last_name, msg.username)}, "
                                  "retiramos tu mensaje para cuidar tu privacidad. No estás solo/a: "
                                  "Línea de la Vida 800 911 2000 (gratuita, 24 h). Si escribes /start al bot "
                                  "en privado podemos enviarte más apoyo.")
        logger.info("crisis_handled", extra={"chat_id": msg.chat_id, "deleted": deleted})
        return {"status": "crisis_support", "deleted": deleted}

    async def _handle_toxic(self, tg: TelegramClient, msg: IncomingMessage, decision: ModerationDecision,
                            thresholds: Thresholds, now: datetime) -> dict[str, Any]:
        deleted = await tg.delete_message(msg.chat_id, msg.message_id)
        max_w = self._settings.max_warnings
        try:
            with session_scope() as s:
                member = repo.lock_member(s, msg.chat_id, msg.user_id)
                member.warnings += 1
                member.last_incident_at = now
                ban = member.warnings >= max_w and not member.is_banned
                if ban:
                    member.is_banned, member.banned_at = True, now
                action = (ActionTaken.DELETED_BANNED if ban
                          else ActionTaken.DELETED_WARNED if deleted else ActionTaken.LOGGED_ONLY)
                incident = self._new_incident(msg, decision, action, crisis=False)
                s.add(incident)
                repo.bump_hourly(s, msg.chat_id, now, flagged=1)
                s.flush()
                incident_id, warnings = incident.id, member.warnings
        except IntegrityError:
            return {"status": "duplicate"}

        who = mention_html(msg.user_id, msg.first_name, msg.last_name, msg.username)
        if ban:
            try:
                await tg.ban_chat_member(msg.chat_id, msg.user_id)
            except TelegramAPIError as exc:
                logger.warning("ban_failed", extra={"chat_id": msg.chat_id, "reason": exc.description})
            await self._safe_send(tg, msg.chat_id,
                                  f"{who} fue retirado del grupo tras acumular {max_w} advertencias "
                                  "por lenguaje ofensivo.")
        else:
            buttons = [{"text": "Retirar mensaje", "callback_data": f"rv:{incident_id}:w"}]
            if can_republish(decision.toxicity, thresholds, self._settings.allow_republish):
                buttons.append({"text": "Publicar de todos modos", "callback_data": f"rv:{incident_id}:p"})
            text = (f"Hola {who}. Retiramos tu mensaje porque puede resultar hiriente o generar un ambiente "
                    f"hostil.\n\n<i>No envíes mensajes que no te gustaría recibir.</i>\n\n"
                    f"Advertencia {warnings} de {max_w}. Al llegar a {max_w} se retira a la persona del grupo.")
            warning_id = await self._safe_send(tg, msg.chat_id, text, reply_markup={"inline_keyboard": [buttons]})
            if warning_id:
                with session_scope() as s:
                    inc = s.get(Incident, incident_id)
                    if inc:
                        inc.warning_message_id = warning_id
        logger.info("incident_recorded", extra={"incident_id": incident_id, "chat_id": msg.chat_id,
                                                "user_id": msg.user_id, "score": decision.toxicity,
                                                "warnings": warnings, "banned": ban})
        return {"status": "incident", "incident_id": incident_id, "banned": ban}

    @staticmethod
    async def _safe_send(tg: TelegramClient, chat_id: int, text: str,
                         reply_markup: dict[str, Any] | None = None) -> int | None:
        try:
            return await tg.send_message(chat_id, text, reply_markup=reply_markup)
        except TelegramTransientError:
            raise
        except TelegramAPIError as exc:
            logger.warning("notify_failed", extra={"chat_id": chat_id, "reason": exc.description})
            return None

    # ----------------------------------------------------------------- botones
    async def handle_callback(self, cb: IncomingCallback) -> dict[str, Any]:
        try:
            _, raw_id, op = cb.data.split(":")
            incident_id = int(raw_id)
        except ValueError:
            return {"status": "malformed"}

        async with httpx.AsyncClient(timeout=15) as http:
            tg = self._telegram(http)
            with session_scope() as s:
                incident = s.get(Incident, incident_id)
                if incident is None:
                    await tg.answer_callback(cb.callback_id, "Esta interacción ya no está disponible.", alert=True)
                    return {"status": "missing"}
                if cb.from_user_id != incident.user_id:
                    await tg.answer_callback(cb.callback_id,
                                             "Solo la persona que escribió el mensaje puede usar estos botones.",
                                             alert=True)
                    return {"status": "forbidden"}
                if incident.user_response is not None:
                    await tg.answer_callback(cb.callback_id, "Ya respondiste a este aviso.")
                    return {"status": "already_answered"}
                author = s.get(TelegramUser, incident.user_id)
                author_name = (mention_html(author.id, author.first_name, author.last_name, author.username)
                               if author else "Usuario")
                thresholds = self._thresholds(incident.group.toxicity_threshold)

                if op == "w":
                    incident.user_response = UserResponse.WITHDRAWN
                    await tg.answer_callback(cb.callback_id, "Gracias por reconsiderarlo.")
                    await tg.delete_message(cb.chat_id, cb.message_id)
                    return {"status": "withdrawn"}
                if op == "p" and can_republish(incident.toxicity_score, thresholds, self._settings.allow_republish):
                    incident.user_response = UserResponse.REPUBLISHED
                    await tg.answer_callback(cb.callback_id, "Mensaje publicado.")
                    await tg.edit_message_text(
                        cb.chat_id, cb.message_id,
                        f"Mensaje de {author_name}, publicado tras una advertencia:\n\n"
                        f"{html.escape(incident.message_text)}")
                    return {"status": "republished"}
                await tg.answer_callback(cb.callback_id, "Este mensaje no puede volver a publicarse.", alert=True)
                return {"status": "blocked"}

    # ------------------------------------------------------------ membresías
    def handle_membership(self, change: MembershipChange) -> dict[str, Any]:
        bot_admin.save_permissions(change.chat_id, change.chat_title, change.chat_type, change.new_status,
                                   change.can_delete_messages, change.can_restrict_members)
        logger.info("bot_membership", extra={"chat_id": change.chat_id, "status": change.new_status})
        return {"status": change.new_status}

    async def handle_group_command(self, cmd: GroupCommand) -> dict[str, Any]:
        """/registrar o /estado: registra el grupo, revisa permisos y responde en el grupo."""
        async with httpx.AsyncClient(timeout=15) as http:
            tg = self._telegram(http)
            info = await bot_admin.refresh_group(tg, cmd.chat_id)
            me = await tg.get_me()
            text = bot_admin.describe(str(info["bot_status"]), info["can_delete"], info["can_restrict"],
                                      bool(me.get("can_read_all_group_messages")))
            await self._safe_send(tg, cmd.chat_id, html.escape(text))
        logger.info("group_registered", extra={"chat_id": cmd.chat_id, "status": info["bot_status"]})
        return {"status": "registered", **info}

    async def handle_private_start(self, chat_id: int, first_name: str) -> None:
        async with httpx.AsyncClient(timeout=15) as http:
            await self._telegram(http).send_message(
                chat_id,
                f"Hola {html.escape(first_name)}. Soy el asistente de convivencia de tus grupos: retiro mensajes "
                "que pueden lastimar y, si alguien está pasando por un momento difícil, le comparto apoyo.\n\n"
                "Línea de la Vida (México): 800 911 2000, gratuita y 24 h.",
            )

