import type { ActionTaken, HateCategory, MacroCategory } from "./types";

export type ChartMacro = Exclude<MacroCategory, "none">;

/** Orden fijo de las series: el color sigue a la entidad, nunca a su rango. */
export const MACROS: { key: ChartMacro; label: string; color: string }[] = [
  { key: "identity_hate", label: "Odio por identidad", color: "var(--s-identity)" },
  { key: "aggression", label: "Agresión y acoso", color: "var(--s-aggression)" },
  { key: "sexual", label: "Contenido sexual", color: "var(--s-sexual)" },
  { key: "crisis", label: "Riesgo / crisis", color: "var(--s-crisis)" },
];

export const MACRO_COLOR: Record<MacroCategory, string> = {
  identity_hate: "var(--s-identity)",
  aggression: "var(--s-aggression)",
  sexual: "var(--s-sexual)",
  crisis: "var(--s-crisis)",
  none: "var(--s-volume)",
};

export const CATEGORY_LABEL: Record<HateCategory, string> = {
  racism: "Racismo",
  xenophobia: "Xenofobia",
  misogyny: "Misoginia / sexismo",
  lgbtq_phobia: "LGBTIQ+fobia",
  religious: "Odio religioso",
  ableism: "Capacitismo",
  identity_other: "Identidad (otro)",
  insult: "Insulto",
  harassment: "Acoso",
  threat: "Amenaza / violencia",
  sexual: "Contenido sexual",
  self_harm: "Riesgo de autolesión",
  none: "Sin categoría",
};

export const CATEGORY_MACRO: Record<HateCategory, MacroCategory> = {
  racism: "identity_hate",
  xenophobia: "identity_hate",
  misogyny: "identity_hate",
  lgbtq_phobia: "identity_hate",
  religious: "identity_hate",
  ableism: "identity_hate",
  identity_other: "identity_hate",
  insult: "aggression",
  harassment: "aggression",
  threat: "aggression",
  sexual: "sexual",
  self_harm: "crisis",
  none: "none",
};

export const ACTION_LABEL: Record<ActionTaken, string> = {
  deleted_warned: "Borrado y advertencia",
  deleted_banned: "Borrado y expulsión",
  deleted_crisis_support: "Apoyo en crisis",
  logged_only: "Solo registrado",
};

export const ROLE_LABEL = { admin: "Administración", moderator: "Moderación", analyst: "Análisis" } as const;
