"""Motor de moderación: ensamble ponderado o cascada sobre proveedores intercambiables.

Estrategias
-----------
ensemble  Consulta en paralelo (asyncio.gather) a todos los proveedores primarios y
          combina: toxicidad = media ponderada; crisis = máximo (principio de precaución).
cascade   Usa el primer proveedor primario que responda (menor costo / latencia).

Si ningún primario responde, se prueban los de respaldo en orden (modelo local,
heurística). La heurística de crisis se evalúa SIEMPRE como red de seguridad.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from app.domain.categories import MACRO_OF, HateCategory, MacroCategory
from app.nlp.base import (
    AuthProviderError,
    ModerationDecision,
    ModerationProvider,
    ProviderError,
    ProviderVerdict,
    RateLimitedError,
)
from app.nlp.providers.heuristic import SAFETY_CATEGORIES, HeuristicProvider

if TYPE_CHECKING:
    import httpx

    from app.core.config import Settings

logger = logging.getLogger(__name__)


def aggregate(
    verdicts: Sequence[ProviderVerdict],
    safety: ProviderVerdict,
    weights: dict[str, float],
    failures: dict[str, str] | None = None,
) -> ModerationDecision:
    """Combina veredictos. Función pura: fácil de probar y de justificar en la tesis.

    1. Puntaje = 0.5 * media ponderada + 0.5 * máximo. La media sola diluye: si un
       modelo detecta misoginia con 0.9 y otro, más débil, da 0.4, la media (0.65)
       quedaría bajo el umbral aunque el contenido sea claramente dañino.
    2. Odio por identidad: si alguna subcategoría (misoginia, LGBTIQ+fobia, racismo...)
       es alta, la toxicidad global no puede ser menor que ella. Un mensaje sexista
       sin groserías es tan dañino como un insulto.
    3. Red de seguridad léxica para odio por identidad, amenazas y crisis.
    """
    pool = list(verdicts) or [safety]

    def blend(values: list[tuple[float, float]]) -> float:
        total_w = sum(w for _, w in values) or 1.0
        mean = sum(v * w for v, w in values) / total_w
        return 0.5 * mean + 0.5 * max(v for v, _ in values)

    toxicity = blend([(v.toxicity, weights.get(v.provider, 1.0)) for v in pool])
    crisis = max([v.crisis for v in pool] + [safety.crisis])

    per_cat: dict[HateCategory, list[tuple[float, float]]] = {}
    for verdict in pool:
        w = weights.get(verdict.provider, 1.0)
        for cat, score in verdict.categories.items():
            per_cat.setdefault(cat, []).append((score, w))
    category_scores = {cat: blend(vals) for cat, vals in per_cat.items()}

    for cat, score in safety.categories.items():
        if cat in SAFETY_CATEGORIES:
            category_scores[cat] = max(category_scores.get(cat, 0.0), score)
    category_scores[HateCategory.SELF_HARM] = crisis

    identity = {c: s for c, s in category_scores.items() if MACRO_OF[c] is MacroCategory.IDENTITY}
    identity_max = max(identity.values(), default=0.0)
    threat = category_scores.get(HateCategory.THREAT, 0.0)
    toxicity = max(toxicity, identity_max, threat if safety.categories.get(HateCategory.THREAT) else 0.0)

    harmful = {c: s for c, s in category_scores.items() if c is not HateCategory.SELF_HARM and s > 0}
    if harmful:
        best = max(harmful, key=lambda c: harmful[c])
        # El odio por identidad es más específico (y más grave) que un insulto genérico:
        # gana si su puntaje es al menos el 60 % del mayor. Dentro de identidad, se
        # prefiere una subcategoría concreta (misoginia, LGBTIQ+fobia...) sobre "otro".
        if identity_max > 0 and identity_max >= 0.6 * harmful[best]:
            specific = {c: s for c, s in identity.items() if c is not HateCategory.IDENTITY_OTHER and s > 0}
            if specific and max(specific.values()) >= 0.5 * identity_max:
                best = max(specific, key=lambda c: specific[c])
            else:
                best = max(identity, key=lambda c: identity[c])
        category = best
    else:
        category = HateCategory.NONE

    return ModerationDecision(
        toxicity=round(toxicity, 4),
        crisis=round(crisis, 4),
        category=category,
        category_scores={c: round(s, 4) for c, s in category_scores.items()},
        verdicts=list(verdicts),
        failures=dict(failures or {}),
    )


class CircuitBreaker:
    """Aparta temporalmente a los proveedores que fallan para no perder tiempo con ellos.

    El estado vive en memoria del proceso: en un worker de larga duración protege a
    todas las tareas siguientes; en serverless, a las invocaciones que comparten instancia.
    """

    def __init__(self, cooldown_seconds: float) -> None:
        self._cooldown = cooldown_seconds
        self._open_until: dict[str, float] = {}

    def available(self, name: str) -> bool:
        return time.monotonic() >= self._open_until.get(name, 0.0)

    def remaining(self, name: str) -> int:
        return max(0, int(self._open_until.get(name, 0.0) - time.monotonic()))

    def record_failure(self, name: str, exc: BaseException) -> None:
        seconds = self._cooldown
        if isinstance(exc, RateLimitedError) and exc.retry_after:
            seconds = max(seconds, min(exc.retry_after, 3600))
        elif isinstance(exc, AuthProviderError):
            seconds = 1800
        self._open_until[name] = time.monotonic() + seconds

    def record_success(self, name: str) -> None:
        self._open_until.pop(name, None)


class ModerationEngine:
    """Ensamble con respaldo ordenado (failover).

    Recorre la lista de proveedores en orden de prioridad y consulta en paralelo los
    primeros `ensemble_size` disponibles. Por cada uno que falle (429, caída, clave
    inválida, JSON roto) toma el siguiente de la lista, hasta completar el ensamble o
    agotar la lista. Si ninguno responde, deciden las reglas léxicas. `cascade` equivale a ensemble_size = 1.
    """

    def __init__(
        self,
        primary: Sequence[ModerationProvider],
        fallback: Sequence[ModerationProvider],
        *,
        strategy: Literal["ensemble", "cascade"] = "ensemble",
        ensemble_size: int = 2,
        weights: dict[str, float] | None = None,
        timeout_seconds: float = 12.0,
        cooldown_seconds: float = 120.0,
    ) -> None:
        self._primary = list(primary)
        self._fallback = list(fallback)
        self._target = 1 if strategy == "cascade" else max(1, ensemble_size)
        self._weights = weights or {}
        self._timeout = timeout_seconds
        self._safety = HeuristicProvider()
        self.breaker = CircuitBreaker(cooldown_seconds)

    @property
    def provider_names(self) -> list[str]:
        return [p.name for p in self._primary] + [p.name for p in self._fallback]

    def status(self) -> list[dict[str, object]]:
        return [{"name": p.name, "role": role, "available": self.breaker.available(p.name),
                 "cooldown_seconds": self.breaker.remaining(p.name)}
                for role, group in (("primario", self._primary), ("respaldo", self._fallback)) for p in group]

    async def classify(self, text: str, client: httpx.AsyncClient | None = None) -> ModerationDecision:
        if client is None:
            import httpx  # noqa: PLC0415

            async with httpx.AsyncClient(timeout=self._timeout) as own_client:
                return await self._classify(text, own_client)
        return await self._classify(text, client)

    async def _call(self, provider: ModerationProvider, text: str,
                    client: httpx.AsyncClient) -> ProviderVerdict | BaseException:
        try:
            return await asyncio.wait_for(provider.classify(text, client), timeout=self._timeout * 2)
        except (ProviderError, TimeoutError) as exc:
            return exc
        except Exception as exc:  # un proveedor defectuoso no debe tumbar el worker
            logger.exception("nlp_provider_crash", extra={"provider": provider.name})
            return exc

    async def _run(self, providers: Sequence[ModerationProvider], target: int, text: str,
                   client: httpx.AsyncClient, verdicts: list[ProviderVerdict], failures: dict[str, str]) -> None:
        queue = list(providers)
        while len(verdicts) < target and queue:
            batch, queue = queue[: target - len(verdicts)], queue[target - len(verdicts):]
            results = await asyncio.gather(*(self._call(p, text, client) for p in batch))
            for provider, result in zip(batch, results, strict=True):
                if isinstance(result, ProviderVerdict):
                    verdicts.append(result)
                    self.breaker.record_success(provider.name)
                else:
                    failures[provider.name] = (str(result) or type(result).__name__)[:200]
                    self.breaker.record_failure(provider.name, result)
                    logger.warning("nlp_failover", extra={"provider": provider.name, "error": failures[provider.name]})

    async def _classify(self, text: str, client: httpx.AsyncClient) -> ModerationDecision:
        verdicts: list[ProviderVerdict] = []
        failures: dict[str, str] = {}

        ready = [p for p in self._primary if self.breaker.available(p.name)]
        for p in self._primary:
            if p not in ready:
                failures[p.name] = f"en espera {self.breaker.remaining(p.name)} s tras un fallo reciente"
        # Si todos están en espera, se intenta igualmente (puede que ya se hayan recuperado).
        await self._run(ready or self._primary, self._target, text, client, verdicts, failures)

        if not verdicts:
            await self._run(self._fallback, 1, text, client, verdicts, failures)

        return aggregate(verdicts, self._safety.classify_sync(text), self._weights, failures)


# Proveedores con API compatible con OpenAI Chat Completions (todos con capa gratuita).
OPENAI_COMPATIBLE: dict[str, tuple[str, str, str, bool]] = {
    # nombre: (base_url, atributo de clave, atributo de modelo, soporta response_format json)
    "groq": ("https://api.groq.com/openai/v1", "groq_api_key", "groq_model", True),
    "cerebras": ("https://api.cerebras.ai/v1", "cerebras_api_key", "cerebras_model", False),
    "openrouter": ("https://openrouter.ai/api/v1", "openrouter_api_key", "openrouter_model", False),
    # Eden AI: pasarela de pago por uso (consume créditos); modelos como "proveedor/modelo".
    "edenai": ("https://api.edenai.run/v3", "edenai_api_key", "edenai_model", False),
}


def build_engine(settings: Settings) -> ModerationEngine:
    """Fábrica: registra solo los proveedores con credenciales configuradas."""
    from app.nlp.providers.llm_judge import OpenAICompatibleJudge  # noqa: PLC0415

    attempts = settings.nlp_max_attempts

    def make(name: str) -> ModerationProvider | None:
        if name in OPENAI_COMPATIBLE:
            base_url, key_attr, model_attr, json_mode = OPENAI_COMPATIBLE[name]
            key = getattr(settings, key_attr)
            if key is None:
                return None
            return OpenAICompatibleJudge(name=name, base_url=base_url, api_key=key.get_secret_value(),
                                         model=getattr(settings, model_attr), max_attempts=attempts,
                                         json_mode=json_mode)
        if name == "heuristic":
            return HeuristicProvider()
        return None

    primary = [p for n in settings.primary_provider_names if (p := make(n))]
    fallback = [p for n in settings.fallback_provider_names if (p := make(n))]
    if not any(p.name == "heuristic" for p in fallback):
        fallback.append(HeuristicProvider())
    engine = ModerationEngine(primary, fallback, strategy=settings.nlp_strategy,
                              ensemble_size=settings.nlp_ensemble_size, weights=settings.provider_weight_map,
                              timeout_seconds=settings.nlp_timeout_seconds,
                              cooldown_seconds=settings.provider_cooldown_seconds)
    logger.info("nlp_engine_ready", extra={"providers": engine.provider_names, "strategy": settings.nlp_strategy})
    return engine
