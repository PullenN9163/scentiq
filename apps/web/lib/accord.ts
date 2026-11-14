import type { CSSProperties } from "react";

/**
 * The ten accord families that give every fragrance its color, plus neutral
 * for a fragrance with no recorded accord.
 */
export const ACCORD_KEYS = [
  "woody",
  "fresh",
  "amber",
  "floral",
  "green",
  "citrus",
  "spicy",
  "musk",
  "gourmand",
  "aquatic",
  "neutral",
] as const;

export type AccordKey = (typeof ACCORD_KEYS)[number];

/** Readable names for the families, in sentence case. */
export const ACCORD_LABELS: Record<AccordKey, string> = {
  woody: "Woody",
  fresh: "Fresh",
  amber: "Amber",
  floral: "Floral",
  green: "Green",
  citrus: "Citrus",
  spicy: "Spicy",
  musk: "Musk",
  gourmand: "Gourmand",
  aquatic: "Aquatic",
  neutral: "Other",
};

/**
 * Catalog accord words mapped to a family. Checked in this order, so a label
 * such as "fresh spicy" resolves to the more distinctive family (spicy).
 * Keywords match whole words, case-insensitively.
 */
const KEYWORDS: [AccordKey, string[]][] = [
  ["spicy", ["warm spicy", "soft spicy", "fresh spicy", "spicy", "spice", "spices", "pepper", "cinnamon"]],
  ["citrus", ["citrus", "citrusy", "bergamot", "lemon"]],
  ["aquatic", ["aquatic", "marine", "ozonic", "salty", "sea"]],
  ["gourmand", ["sweet", "vanilla", "gourmand", "fruity", "fruit", "honey", "caramel", "chocolate", "coffee", "lactonic", "cherry", "almond"]],
  ["floral", ["white floral", "yellow floral", "floral", "flowers", "rose", "iris", "violet", "tuberose", "jasmine"]],
  ["amber", ["amber", "ambery", "oriental", "resin", "resinous", "balsamic", "incense", "tobacco", "warm"]],
  ["woody", ["woody", "wood", "woods", "cedar", "sandalwood", "oud", "vetiver", "patchouli", "leather", "smoky", "earthy"]],
  ["green", ["green", "aromatic", "herbal", "mossy", "lavender", "fougere", "fougère", "tea"]],
  ["musk", ["musk", "musky", "powdery", "animalic", "white musk"]],
  ["fresh", ["fresh", "clean", "soapy", "aldehydic", "metallic"]],
];

const PATTERNS: [AccordKey, RegExp][] = KEYWORDS.map(([key, words]) => [
  key,
  new RegExp(`(?:^|[^\\p{L}])(?:${words.map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})(?:$|[^\\p{L}])`, "iu"),
]);

/** The family for one catalog label, or neutral when nothing matches. */
export function accordFromLabel(label: string | null | undefined): AccordKey {
  const value = label?.trim();
  if (!value) return "neutral";
  for (const [key, pattern] of PATTERNS) {
    if (pattern.test(value)) return key;
  }
  return "neutral";
}

/**
 * The family a fragrance wears: its first top accord, then its olfactory
 * family, then neutral.
 */
export function accordFor(fragrance: {
  top_accords?: readonly string[] | null;
  olfactory_family?: string | null;
}): AccordKey {
  const first = fragrance.top_accords?.find((accord) => accord && accord.trim());
  const fromAccord = accordFromLabel(first);
  if (fromAccord !== "neutral") return fromAccord;
  return accordFromLabel(fragrance.olfactory_family);
}

/** Inline custom properties for a plate, hero, vial or chart segment. */
export function accordVars(key: AccordKey): CSSProperties {
  const chart = key === "neutral" ? "musk" : key;
  return {
    "--af": `var(--accord-${key}-field)`,
    "--ad": `var(--accord-${key}-deep)`,
    "--ac": `var(--chart-${chart})`,
  } as CSSProperties;
}
