"""Laboratorio: clasifica un texto SIN publicarlo ni registrarlo.

Sirve para calibrar umbrales y explicar en la presentación por qué un mensaje se
borraría o no, mostrando el veredicto de cada modelo.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import DbSession, ModeratorUser
from app.core.config import get_settings
from app.db.models import TelegramGroup
from app.domain.categories import MACRO_OF, HateCategory, MacroCategory
from app.nlp.providers.heuristic import HeuristicProvider
from app.services.policy import build_thresholds, decide, identity_score
from app.workers.handlers import get_engine_instance

router = APIRouter(prefix="/moderation", tags=["moderation"])


class TestRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    group_id: int | None = None


class ProviderResult(BaseModel):
    name: str
    toxicity: float | None = None
    crisis: float | None = None
    latency_ms: float | None = None
    rationale: str | None = None
    top_category: HateCategory | None = None
    error: str | None = None


class TestResult(BaseModel):
    verdict: str
    toxicity: float
    crisis: float
    identity: float
    category: HateCategory
    macro: MacroCategory
    category_scores: dict[HateCategory, float]
    thresholds: dict[str, float]
    providers: list[ProviderResult]
    safety_net: str | None


@router.post("/test", response_model=TestResult)
async def test_message(body: TestRequest, _: ModeratorUser, db: DbSession) -> TestResult:
    override = None
    if body.group_id is not None:
        group = db.get(TelegramGroup, body.group_id)
        override = group.toxicity_threshold if group else None
    thresholds = build_thresholds(get_settings(), override)
    decision = await get_engine_instance().classify(body.text)
    verdict = decide(decision, thresholds)
    safety = HeuristicProvider().classify_sync(body.text)

    providers = [
        ProviderResult(
            name=v.provider, toxicity=round(v.toxicity, 3), crisis=round(v.crisis, 3),
            latency_ms=round(v.latency_ms, 1), rationale=v.rationale,
            top_category=max(v.categories, key=lambda c: v.categories[c]) if v.categories else None,
        )
        for v in decision.verdicts
    ] + [ProviderResult(name=name, error=err) for name, err in decision.failures.items()]

    return TestResult(
        verdict=verdict.value,
        toxicity=decision.toxicity,
        crisis=decision.crisis,
        identity=round(identity_score(decision), 4),
        category=decision.category,
        macro=MACRO_OF[decision.category],
        category_scores={c: s for c, s in sorted(decision.category_scores.items(), key=lambda kv: -kv[1]) if s > 0},
        thresholds={"toxicity": thresholds.toxicity, "identity": thresholds.identity, "crisis": thresholds.crisis,
                    "hard_block": thresholds.hard_block},
        providers=providers,
        safety_net=safety.rationale,
    )
