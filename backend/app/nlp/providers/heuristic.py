"""Red de seguridad léxica: sin red, sin costo, siempre disponible.

Dos usos:
1. Respaldo final cuando ningún modelo responde.
2. Red de seguridad SIEMPRE activa para crisis, odio por identidad y amenazas:
   el motor toma el máximo entre lo que digan los modelos y estas reglas, de modo
   que un insulto homofóbico o sexista explícito nunca depende de que un LLM lo note.
"""

from __future__ import annotations

import re
import time
import unicodedata
from typing import TYPE_CHECKING

from app.domain.categories import HateCategory
from app.nlp.base import ProviderVerdict

if TYPE_CHECKING:
    import httpx


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    # leetspeak frecuente: 3->e, 4->a, 0->o, 1->i, @->a, $->s
    text = text.translate(str.maketrans("3401@$", "eaoias"))
    # letras repetidas para evadir filtros: "jotooo" -> "joto"
    text = re.sub(r"(\w)\1{2,}", r"\1", text)
    # separadores intercalados: "m.a.r.i.c.o.n" -> "maricon"
    return re.sub(r"(?<=\w)[.\-_*](?=\w)", "", text)


CRISIS_PATTERNS = [
    r"\bsuicid", r"\bmatarme\b", r"\bquitarme la vida\b", r"\bno quiero (seguir )?vivir\b",
    r"\bacabar con todo\b", r"\bya no aguanto\b", r"\bme quiero morir\b", r"\bdesaparecer para siempre\b",
    r"\bhacerme dano\b", r"\bcortarme\b",
]

# Términos de grupo (para frases estereotipadas que no contienen insultos).
WOMEN = r"(las )?(mujeres|viejas|chavas|morras|ninas|feministas)"
LGBT = (r"(los |las )?(gays?|homosexual(es)?|lesbianas?|trans(exuales)?|transgenero|bisexual(es)?"
        r"|lgbt\w*|jotos?|maricones?|travestis?|la gente (gay|trans|lgbt\w*)|esa gente)")

# Puntaje base por categoría cuando hay coincidencia (los slurs son graves por sí solos).
SCORES: dict[HateCategory, float] = {
    HateCategory.INSULT: 0.75,
    HateCategory.MISOGYNY: 0.85,
    HateCategory.LGBTQ_PHOBIA: 0.88,
    HateCategory.RACISM: 0.88,
    HateCategory.XENOPHOBIA: 0.85,
    HateCategory.ABLEISM: 0.8,
    HateCategory.THREAT: 0.9,
}

LEXICON: dict[HateCategory, list[str]] = {
    HateCategory.INSULT: [
        r"\bpendej[oa]s?\b", r"\bimbecil(es)?\b", r"\bestupid[oa]s?\b", r"\bidiota?s?\b", r"\binutil(es)?\b",
        r"\bculer[oa]s?\b", r"\bbabos[oa]s?\b", r"\bmamon(a|es)?\b", r"\bhij[oa]s? de (puta|perra)\b",
    ],
    HateCategory.MISOGYNY: [
        r"\b(eres|pinche|maldita|esa|una|vieja|pinches|malditas|esas|son unas) (perras?|zorras?|golfas?|putas?)\b",
        r"(?<!hijo de )\bputas?\b(?! madre)",
        r"\bvieja (loca|histerica|estupida|pendeja)\b", r"\bpinches? viejas?\b", r"\bfeminazis?\b",
        r"\b(vete|regresa|regresate|ve) a (la )?(cocina|lavar|planchar)\b", r"\bmujer (tenias|tenia) que ser\b",
        r"\bpor eso (las )?mujeres\b", r"\bcomo (vieja|nina|mujer)\b.{0,20}\b(lloras|chillas|maneja)",
        rf"\b{WOMEN}\b.{{0,30}}\b(no (deberian (opinar|hablar|trabajar|votar|estudiar|mandar|programar|manejar|liderar|jugar|estar aqui)|sirven|saben (nada|programar|manejar)|pueden (liderar|mandar|programar))|son (un[oa]s )?(inferiores|tontas|menos|"
        r"emocionales|histericas|interesadas|para la casa)|solo sirven|deberian (callarse|estar en))",
        r"\bno es trabajo (de|para) (mujeres|viejas)\b", r"\bse lo busco por (vestirse|como se vestia)\b",
    ],
    HateCategory.LGBTQ_PHOBIA: [
        r"\bjot[oa]s?\b", r"\bjotit[oa]s?\b", r"\bmaric(a|on|ones|ona|onazo)\b", r"\bmariposon(es)?\b",
        r"\bpunal(es)?\b", r"\btortilleras?\b", r"\blenchas?\b", r"\bmachorras?\b",
        r"\bmaricadas?\b", r"\bde (jotos|maricas|maricones)\b", r"\bse le (cae|moja) la (mano|canoa)\b",
        r"\bpinche (gay|joto|trans|lesbiana)\b", r"\bes de (gays|jotos)\b",
        rf"\b{LGBT}\b.{{0,40}}\b(son|estan|esta|es)\b.{{0,15}}\b(enferm[oa]s?|asquerosos?|aberracion|anormal(es)?"
        r"|degenerad[oa]s?|pecadores?|abominacion|un error|una plaga)",
        rf"\b{LGBT}\b.{{0,40}}\b(no (es|son) natural(es)?|deberian (curarse|morir|desaparecer|no existir)"
        r"|no deberian (existir|adoptar|casarse)|me dan asco|dan asco|al infierno|hay que (curar|quemar))",
        r"\b(eso|ser gay|ser trans|la homosexualidad)\b.{0,15}\b(es|son) (una )?(enfermedad|aberracion|pecado|moda)",
        r"\bmuerte a los\b.{0,15}\b(gays?|jotos|maricones|trans)\b",
    ],
    HateCategory.RACISM: [
        r"\bindio pata rajada\b", r"\bprieto asqueroso\b", r"\bsimios?\b", r"\bnegros? de mierda\b",
        r"\bpinche (indio|prieto|negro|naco)\b", r"\bpor tu color\b",
    ],
    HateCategory.XENOPHOBIA: [
        r"\bregresate a tu pais\b", r"\b(pinches?|malditos?) (migrantes|extranjeros|venezolanos|centroamericanos"
        r"|hondurenos|chinos|gringos)\b", r"\bnos (vienen a quitar|quitan) (todo|el trabajo)\b",
    ],
    HateCategory.ABLEISM: [r"\bretrasad[oa]s?\b", r"\bmongolit[oa]s?\b", r"\bsubnormal(es)?\b", r"\bautista\b.{0,10}\b(eres|pareces)"],
    HateCategory.THREAT: [r"\bte voy a (matar|partir|romper|violar)\b", r"\bte (mato|parto la madre)\b",
                          r"\bse donde vives\b", r"\bte espero a la salida\b", r"\bhay que matar(los|las)?\b"],
}

# Groserías coloquiales sin destinatario ("qué pinche calor"): por sí solas no
# superan el umbral; suman si acompañan a un insulto dirigido.
MILD_PROFANITY = re.compile(r"\bmierda\b|\bpinche\b|\bcabron(a|es)?\b|\bchingad[oa]\b|\bverga\b|\bputo\b")
SECOND_PERSON = re.compile(r"\b(eres|tu|te|estas|vales)\b")

_CRISIS_RE = re.compile("|".join(CRISIS_PATTERNS))
_LEXICON_RE = {cat: re.compile("|".join(pats)) for cat, pats in LEXICON.items()}

# Categorías que la red de seguridad impone aunque los modelos no las detecten.
SAFETY_CATEGORIES = frozenset({
    HateCategory.MISOGYNY, HateCategory.LGBTQ_PHOBIA, HateCategory.RACISM,
    HateCategory.XENOPHOBIA, HateCategory.ABLEISM, HateCategory.THREAT,
})


class HeuristicProvider:
    name = "heuristic"

    async def classify(self, text: str, client: httpx.AsyncClient | None = None) -> ProviderVerdict:
        return self.classify_sync(text)

    def classify_sync(self, text: str) -> ProviderVerdict:
        start = time.perf_counter()
        norm = normalize(text)
        crisis = 0.9 if _CRISIS_RE.search(norm) else 0.0
        categories: dict[HateCategory, float] = {}
        hits_found: list[str] = []
        for category, pattern in _LEXICON_RE.items():
            matches = [m.group(0) for m in pattern.finditer(norm)]
            if matches:
                categories[category] = min(1.0, SCORES[category] + 0.05 * (len(matches) - 1))
                hits_found.extend(matches)
        mild = len(MILD_PROFANITY.findall(norm))
        if mild:
            directed = 0.25 if SECOND_PERSON.search(norm) else 0.0
            base = categories.get(HateCategory.INSULT, 0.0)
            categories[HateCategory.INSULT] = min(1.0, max(base + 0.05 * mild, 0.35 + directed + 0.05 * (mild - 1)))
        if crisis:
            categories[HateCategory.SELF_HARM] = crisis
        toxicity = max((s for c, s in categories.items() if c is not HateCategory.SELF_HARM), default=0.0)
        return ProviderVerdict(
            provider=self.name,
            toxicity=toxicity,
            crisis=crisis,
            categories=categories,
            latency_ms=(time.perf_counter() - start) * 1000,
            rationale=("coincidencias: " + ", ".join(sorted(set(hits_found)))[:200]) if hits_found else None,
        )
