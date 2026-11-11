"""POST JSON con reintentos y backoff exponencial con jitter (tenacity)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.nlp.base import AuthProviderError, ProviderError, RateLimitedError, TransientProviderError

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 409, 425, 500, 502, 503, 504}


async def post_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    provider: str,
    max_attempts: int,
) -> dict[str, Any]:
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(TransientProviderError),
        wait=wait_exponential_jitter(initial=0.5, max=8.0),
        stop=stop_after_attempt(max_attempts),
        reraise=True,
    ):
        with attempt:
            n = attempt.retry_state.attempt_number
            try:
                response = await client.post(url, headers=headers, json=payload)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                logger.warning("nlp_transient_network", extra={"provider": provider, "attempt": n, "error": str(exc)})
                raise TransientProviderError(f"{provider}: {type(exc).__name__}") from exc
            if response.status_code == 429:
                raw = response.headers.get("retry-after")
                retry_after = float(raw) if raw and raw.replace(".", "", 1).isdigit() else None
                logger.warning("nlp_rate_limited", extra={"provider": provider, "retry_after": retry_after})
                raise RateLimitedError(f"{provider}: límite de uso alcanzado (429)", retry_after)
            if response.status_code in (401, 403):
                raise AuthProviderError(f"{provider}: clave inválida o sin permisos ({response.status_code})")
            if response.status_code in RETRYABLE_STATUS:
                logger.warning("nlp_transient_status",
                               extra={"provider": provider, "attempt": n, "status": response.status_code})
                raise TransientProviderError(f"{provider}: HTTP {response.status_code}")
            if response.status_code >= 400:
                raise ProviderError(f"{provider}: HTTP {response.status_code} {response.text[:200]}")
            data: dict[str, Any] = response.json()
            return data
    raise ProviderError(f"{provider}: sin respuesta")  # pragma: no cover
