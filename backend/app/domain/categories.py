"""Taxonomía de contenido dañino (dos niveles: macro -> subcategoría).

La jerarquía alimenta la dona multicapa del panel: el anillo interior es la
macrocategoría y el exterior la subcategoría.
"""

from __future__ import annotations

from enum import StrEnum


class MacroCategory(StrEnum):
    IDENTITY = "identity_hate"
    AGGRESSION = "aggression"
    SEXUAL = "sexual"
    CRISIS = "crisis"
    NONE = "none"


class HateCategory(StrEnum):
    RACISM = "racism"
    XENOPHOBIA = "xenophobia"
    MISOGYNY = "misogyny"
    LGBTQ_PHOBIA = "lgbtq_phobia"
    RELIGIOUS = "religious"
    ABLEISM = "ableism"
    IDENTITY_OTHER = "identity_other"
    INSULT = "insult"
    HARASSMENT = "harassment"
    THREAT = "threat"
    SEXUAL = "sexual"
    SELF_HARM = "self_harm"
    NONE = "none"


MACRO_OF: dict[HateCategory, MacroCategory] = {
    HateCategory.RACISM: MacroCategory.IDENTITY,
    HateCategory.XENOPHOBIA: MacroCategory.IDENTITY,
    HateCategory.MISOGYNY: MacroCategory.IDENTITY,
    HateCategory.LGBTQ_PHOBIA: MacroCategory.IDENTITY,
    HateCategory.RELIGIOUS: MacroCategory.IDENTITY,
    HateCategory.ABLEISM: MacroCategory.IDENTITY,
    HateCategory.IDENTITY_OTHER: MacroCategory.IDENTITY,
    HateCategory.INSULT: MacroCategory.AGGRESSION,
    HateCategory.HARASSMENT: MacroCategory.AGGRESSION,
    HateCategory.THREAT: MacroCategory.AGGRESSION,
    HateCategory.SEXUAL: MacroCategory.SEXUAL,
    HateCategory.SELF_HARM: MacroCategory.CRISIS,
    HateCategory.NONE: MacroCategory.NONE,
}

LABEL_ES: dict[HateCategory, str] = {
    HateCategory.RACISM: "Racismo",
    HateCategory.XENOPHOBIA: "Xenofobia",
    HateCategory.MISOGYNY: "Misoginia / sexismo",
    HateCategory.LGBTQ_PHOBIA: "LGBTIQ+fobia",
    HateCategory.RELIGIOUS: "Odio religioso",
    HateCategory.ABLEISM: "Capacitismo",
    HateCategory.IDENTITY_OTHER: "Odio por identidad (otro)",
    HateCategory.INSULT: "Insulto",
    HateCategory.HARASSMENT: "Acoso",
    HateCategory.THREAT: "Amenaza / violencia",
    HateCategory.SEXUAL: "Contenido sexual",
    HateCategory.SELF_HARM: "Riesgo de autolesión",
    HateCategory.NONE: "Sin categoría",
}

MACRO_LABEL_ES: dict[MacroCategory, str] = {
    MacroCategory.IDENTITY: "Odio por identidad",
    MacroCategory.AGGRESSION: "Agresión y acoso",
    MacroCategory.SEXUAL: "Contenido sexual",
    MacroCategory.CRISIS: "Riesgo / crisis",
    MacroCategory.NONE: "Sin categoría",
}


def macro_of(category: HateCategory) -> MacroCategory:
    return MACRO_OF[category]
