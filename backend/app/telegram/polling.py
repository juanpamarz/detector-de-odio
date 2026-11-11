"""Gateway de long-polling para desarrollo local (sin URL pública).

Hace lo mismo que el webhook: recibe Updates y los encola. En la nube (Vercel) se usa el
webhook (`python -m app.cli set-webhook`) y este servicio no se despliega.

    python -m app.telegram.polling
"""

from __future__ import annotations

import logging
import signal
import time
from types import FrameType

import httpx

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.telegram.dispatcher import ALLOWED_UPDATES, route_update

logger = logging.getLogger("gateway")
_running = True


def _stop(signum: int, _frame: FrameType | None) -> None:
    global _running
    _running = False
    logger.info("gateway_stopping", extra={"signal": signum})


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.telegram_bot_token:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN")
    base = f"https://api.telegram.org/bot{settings.telegram_bot_token.get_secret_value()}"
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    offset = 0
    backoff = 1.0
    with httpx.Client(timeout=httpx.Timeout(40.0, connect=10.0)) as client:
        client.post(f"{base}/deleteWebhook")
        me = client.get(f"{base}/getMe").json().get("result", {})
        logger.info("gateway_ready", extra={"bot": me.get("username")})
        while _running:
            try:
                resp = client.post(f"{base}/getUpdates",
                                   json={"offset": offset, "timeout": 25, "allowed_updates": ALLOWED_UPDATES})
                resp.raise_for_status()
                for update in resp.json().get("result", []):
                    offset = int(update["update_id"]) + 1
                    kind = route_update(update)
                    logger.info("update_enqueued", extra={"update_id": update["update_id"], "kind": kind})
                backoff = 1.0
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("gateway_error", extra={"error": type(exc).__name__, "retry_in": backoff})
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)


if __name__ == "__main__":
    main()
