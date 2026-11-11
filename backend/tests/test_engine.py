"""Pruebas de la lógica pura: heurística, agregación del ensamble y política."""

from __future__ import annotations

import asyncio

from app.domain.categories import HateCategory
from app.nlp.base import ProviderError, ProviderVerdict
from app.nlp.engine import ModerationEngine, aggregate
from app.nlp.providers.heuristic import HeuristicProvider
from app.services.policy import Thresholds, Verdict, can_republish, decide

TH = Thresholds(toxicity=0.7, crisis=0.5, hard_block=0.9)
H = HeuristicProvider()


def v(name: str, tox: float, crisis: float = 0.0, **cats: float) -> ProviderVerdict:
    return ProviderVerdict(name, tox, crisis, {HateCategory(k): s for k, s in cats.items()}, 1.0)


def test_heuristic_detects_directed_insult() -> None:
    out = H.classify_sync("Eres un PENDEJO")
    assert out.toxicity >= 0.75
    assert HateCategory.INSULT in out.categories


def test_heuristic_mild_profanity_alone_is_below_threshold() -> None:
    assert H.classify_sync("qué pinche calor hace hoy").toxicity < TH.toxicity


def test_heuristic_handles_leetspeak_and_accents() -> None:
    assert H.classify_sync("eres un 1mbécil").toxicity >= 0.75


def test_heuristic_crisis() -> None:
    out = H.classify_sync("ya no aguanto, me quiero morir")
    assert out.crisis >= 0.9


def test_aggregate_weighted_mean_and_crisis_max() -> None:
    safety = H.classify_sync("hola")
    d = aggregate([v("a", 0.9, insult=0.9), v("b", 0.5, 0.6, insult=0.4)], safety, {"a": 1.0, "b": 1.0})
    assert abs(d.toxicity - 0.8) < 1e-6  # 0.5 * media (0.7) + 0.5 * máximo (0.9)
    assert d.crisis == 0.6
    assert d.category is HateCategory.INSULT


def test_aggregate_prefers_specific_identity_category() -> None:
    safety = H.classify_sync("hola")
    d = aggregate([v("a", 0.9, identity_other=0.9), v("b", 0.85, misogyny=0.8)], safety, {})
    assert d.category is HateCategory.MISOGYNY


def test_safety_net_raises_crisis_even_if_providers_miss_it() -> None:
    safety = H.classify_sync("estoy pensando en quitarme la vida")
    d = aggregate([v("a", 0.1)], safety, {})
    assert decide(d, TH) is Verdict.CRISIS_SUPPORT


def test_policy_order_and_republish() -> None:
    safety = H.classify_sync("hola")
    assert decide(aggregate([v("a", 0.2)], safety, {}), TH) is Verdict.ALLOW
    assert decide(aggregate([v("a", 0.8)], safety, {}), TH) is Verdict.DELETE_AND_WARN
    assert can_republish(0.8, TH, True) and not can_republish(0.95, TH, True)


class Failing:
    name = "down"

    async def classify(self, text: str, client: object) -> ProviderVerdict:
        raise ProviderError("caído")


def test_engine_falls_back_when_all_primaries_fail() -> None:
    engine = ModerationEngine([Failing()], [HeuristicProvider()])
    d = asyncio.run(engine.classify("eres un idiota", client=object()))  # type: ignore[arg-type]
    assert d.failures == {"down": "caído"}
    assert d.verdicts[0].provider == "heuristic"
    assert d.toxicity >= 0.75


# --- Odio por identidad (sexismo, LGBTIQ+fobia) ------------------------------------

SEXIST = [
    "las mujeres no deberían opinar de programación",
    "vete a la cocina mejor",
    "mujer tenías que ser",
    "eres una pinche zorra",
    "las feministas son unas histericas",
]
LGBTPHOBIC = [
    "qué asco los jotos",
    "ser gay es una enfermedad",
    "los trans no deberían existir",
    "eres un maricón",
    "esa gente lgbt está enferma",
    "jotoooo",
    "m.a.r.i.c.o.n",
]
BENIGN = [
    "mi hermana es lesbiana y la amo",
    "puta madre qué calor hace",
    "mi perra se llama Luna",
    "el machismo es un problema en la facultad",
    "las mujeres de mi equipo programan increíble",
]


def test_heuristic_flags_sexism() -> None:
    for text in SEXIST:
        out = H.classify_sync(text)
        assert out.categories.get(HateCategory.MISOGYNY, 0) >= 0.8, text


def test_heuristic_flags_lgbtphobia() -> None:
    for text in LGBTPHOBIC:
        out = H.classify_sync(text)
        assert out.categories.get(HateCategory.LGBTQ_PHOBIA, 0) >= 0.8, text


def test_heuristic_does_not_flag_benign_mentions() -> None:
    for text in BENIGN:
        assert H.classify_sync(text).toxicity < TH.toxicity, text


def test_safety_net_deletes_identity_hate_even_if_models_score_low() -> None:
    for text in SEXIST + LGBTPHOBIC:
        d = aggregate([v("llm", 0.3, misogyny=0.2)], H.classify_sync(text), {})
        assert decide(d, TH) is Verdict.DELETE_AND_WARN, text
        assert d.category in {HateCategory.MISOGYNY, HateCategory.LGBTQ_PHOBIA}, text


def test_identity_threshold_catches_implicit_hate_from_llm() -> None:
    # Un LLM ve misoginia (0.6) pero da toxicidad global baja (0.4): antes pasaba.
    d = aggregate([v("llm", 0.4, misogyny=0.6), v("otro", 0.3)], H.classify_sync("opinión neutra"), {})
    assert d.category is HateCategory.MISOGYNY
    assert decide(d, TH) is Verdict.DELETE_AND_WARN


def test_identity_category_wins_over_generic_insult() -> None:
    d = aggregate([v("llm", 0.9, insult=0.9, lgbtq_phobia=0.7)], H.classify_sync("hola"), {})
    assert d.category is HateCategory.LGBTQ_PHOBIA


# --- Respaldo ordenado entre modelos (failover) -------------------------------------

class Fake:
    def __init__(self, name: str, tox: float = 0.8, error: Exception | None = None) -> None:
        self.name = name
        self.tox = tox
        self.error = error
        self.calls = 0

    async def classify(self, text: str, client: object) -> ProviderVerdict:
        self.calls += 1
        if self.error:
            raise self.error
        return ProviderVerdict(self.name, self.tox, 0.0, {HateCategory.INSULT: self.tox}, 1.0)


def test_failover_takes_next_provider_when_one_is_rate_limited() -> None:
    from app.nlp.base import RateLimitedError

    groq = Fake("groq", error=RateLimitedError("429"))
    gemini, cerebras, extra = Fake("gemini"), Fake("cerebras"), Fake("openrouter")
    engine = ModerationEngine([groq, gemini, cerebras, extra], [HeuristicProvider()], ensemble_size=2)
    d = asyncio.run(engine.classify("hola", client=object()))  # type: ignore[arg-type]
    assert [x.provider for x in d.verdicts] == ["gemini", "cerebras"]
    assert extra.calls == 0  # no se consulta más de lo necesario
    assert "groq" in d.failures


def test_circuit_breaker_skips_failed_provider_on_next_message() -> None:
    from app.nlp.base import RateLimitedError

    groq = Fake("groq", error=RateLimitedError("429", retry_after=60))
    gemini = Fake("gemini")
    engine = ModerationEngine([groq, gemini], [HeuristicProvider()], strategy="cascade")
    asyncio.run(engine.classify("uno", client=object()))  # type: ignore[arg-type]
    asyncio.run(engine.classify("dos", client=object()))  # type: ignore[arg-type]
    assert groq.calls == 1 and gemini.calls == 2


def test_all_models_down_uses_rules() -> None:
    engine = ModerationEngine([Fake("a", error=ProviderError("x")), Fake("b", error=TimeoutError())],
                              [HeuristicProvider()])
    d = asyncio.run(engine.classify("ser gay es una enfermedad", client=object()))  # type: ignore[arg-type]
    assert d.verdicts[0].provider == "heuristic"
    assert decide(d, TH) is Verdict.DELETE_AND_WARN


def test_llm_judge_switches_model_when_one_is_retired() -> None:
    from app.nlp.providers import llm_judge

    calls: list[str] = []

    async def fake_post(client, url, *, headers, payload, provider, max_attempts):  # type: ignore[no-untyped-def]
        calls.append(payload["model"])
        if payload["model"] == "viejo":
            raise ProviderError("404 model_not_found")
        return {"choices": [{"message": {"content": '{"toxicity": 0.9, "crisis": 0, "categories": {"misogyny": 0.9}}'}}]}

    llm_judge.post_json = fake_post  # type: ignore[assignment]
    judge = llm_judge.OpenAICompatibleJudge(name="groq", base_url="http://x", api_key="k", model="viejo,nuevo",
                                            max_attempts=1)
    out = asyncio.run(judge.classify("texto", client=object()))  # type: ignore[arg-type]
    assert out.categories[HateCategory.MISOGYNY] == 0.9
    asyncio.run(judge.classify("otro", client=object()))  # type: ignore[arg-type]
    assert calls == ["viejo", "nuevo", "nuevo"]  # el que funcionó queda primero
