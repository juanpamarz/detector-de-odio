"""Logging estructurado en JSON (una línea por evento).

Vercel y `docker compose logs` muestran cada evento como un objeto JSON que se
puede filtrar por campo (p. ej. `"msg": "incident_recorded"`). Los secretos se ocultan.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

_RESERVED = set(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
) | {"message", "asctime", "taskName"}


# Patrones de secretos que nunca deben quedar en logs (p. ej. httpx incluye la URL
# https://api.telegram.org/bot<TOKEN>/... en sus mensajes de error).
_SECRETS = re.compile(
    r"(bot)\d{6,}:[A-Za-z0-9_-]{20,}"
    r"|(Bearer )[A-Za-z0-9._~+/=-]{12,}"
    r"|\b(sk-[A-Za-z0-9_-]{2,}|gsk_|csk-|AIza)[A-Za-z0-9._-]{12,}"
)


def redact(text: str) -> str:
    return _SECRETS.sub(lambda m: (m.group(1) or m.group(2) or "") + "[oculto]", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return redact(json.dumps(payload, ensure_ascii=False, default=str))


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpcore", "amqp", "kombu"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # Uvicorn trae sus propios handlers; los redirigimos al root JSON.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
