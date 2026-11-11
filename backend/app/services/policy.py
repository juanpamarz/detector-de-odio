"""Política de moderación: decide la acción a partir de los puntajes (función pura)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from app.domain.categories import MACRO_OF, MacroCategory
from app.nlp.base import ModerationDecision

if TYPE_CHECKING:
    from app.core.config import Settings


class Verdict(StrEnum):
    ALLOW = "allow"
    CRISIS_SUPPORT = "crisis_support"
    DELETE_AND_WARN = "delete_and_warn"


@dataclass(frozen=True, slots=True)
class Thresholds:
    toxicity: float
    crisis: float
    hard_block: float
    # Umbral propio, más estricto, para odio por identidad (sexismo, LGBTIQ+fobia,
    # racismo...): estos mensajes suelen venir sin groserías y los modelos les dan
    # puntajes moderados aunque el daño sea alto.
    identity: float = 0.55


def build_thresholds(settings: Settings, group_override: float | None = None) -> Thresholds:
    toxicity = group_override if group_override is not None else settings.toxicity_threshold
    return Thresholds(
        toxicity=toxicity,
        crisis=settings.crisis_threshold,
        hard_block=settings.hard_block_threshold,
        # Si un grupo se vuelve más estricto, el umbral de identidad también baja.
        identity=min(settings.identity_hate_threshold, toxicity),
    )


def identity_score(decision: ModerationDecision) -> float:
    return max((s for c, s in decision.category_scores.items() if MACRO_OF[c] is MacroCategory.IDENTITY),
               default=0.0)


def decide(decision: ModerationDecision, thresholds: Thresholds) -> Verdict:
    # La crisis tiene prioridad: primero se protege a la persona.
    if decision.crisis >= thresholds.crisis:
        return Verdict.CRISIS_SUPPORT
    if decision.toxicity >= thresholds.toxicity:
        return Verdict.DELETE_AND_WARN
    if identity_score(decision) >= thresholds.identity:
        return Verdict.DELETE_AND_WARN
    return Verdict.ALLOW


def can_republish(toxicity: float, thresholds: Thresholds, allow_republish: bool) -> bool:
    """Por debajo del umbral duro el autor puede insistir en publicar (tu flujo de reflexión)."""
    return allow_republish and toxicity < thresholds.hard_block
