"""Abstracciones del clasificador (Dependency Inversion: el servicio depende del
protocolo, no de Groq/Cerebras/OpenRouter concretos)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from app.domain.categories import HateCategory

if TYPE_CHECKING:
    import httpx


class ProviderError(Exception):
    """Error definitivo del proveedor (credenciales, petición inválida)."""


class TransientProviderError(ProviderError):
    """Error recuperable (timeout, 5xx): se reintenta con backoff dentro del mismo proveedor."""


class RateLimitedError(ProviderError):
    """429 / cuota agotada: no se reintenta; el motor pasa al siguiente proveedor."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class AuthProviderError(ProviderError):
    """Clave inválida o sin permisos (401/403): el proveedor se aparta por más tiempo."""


@dataclass(frozen=True, slots=True)
class ProviderVerdict:
    provider: str
    toxicity: float
    crisis: float
    categories: dict[HateCategory, float]
    latency_ms: float
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class ModerationDecision:
    toxicity: float
    crisis: float
    category: HateCategory
    category_scores: dict[HateCategory, float]
    verdicts: list[ProviderVerdict] = field(default_factory=list)
    failures: dict[str, str] = field(default_factory=dict)

    def providers_summary(self) -> list[dict[str, object]]:
        return [
            {"name": v.provider, "toxicity": round(v.toxicity, 4), "crisis": round(v.crisis, 4),
             "latency_ms": round(v.latency_ms, 1)}
            for v in self.verdicts
        ] + [{"name": name, "error": err} for name, err in self.failures.items()]


@runtime_checkable
class ModerationProvider(Protocol):
    name: str

    async def classify(self, text: str, client: httpx.AsyncClient) -> ProviderVerdict: ...


def clamp(value: object) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))
