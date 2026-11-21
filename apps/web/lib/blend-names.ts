import type { AccordKey } from "@/lib/accord";

/**
 * Words for a generated blend name ("Amber Dusk", "Green Rain"). The first
 * word comes from one of the two strongest accords, the second from a time
 * or weather word. Each accord has two options; the time list has fourteen.
 */
export const ACCORD_WORDS: Record<AccordKey, readonly [string, string]> = {
  woody: ["Cedar", "Driftwood"],
  fresh: ["Silver", "Linen"],
  amber: ["Amber", "Ember"],
  floral: ["Rose", "Velvet"],
  green: ["Mossy", "Fern"],
  citrus: ["Citrus", "Sunlit"],
  spicy: ["Clove", "Smoky"],
  musk: ["Hushed", "Soft"],
  gourmand: ["Honey", "Cocoa"],
  aquatic: ["Tidal", "Salt"],
  neutral: ["Quiet", "Plain"],
};

export const TIME_WORDS = [
  "Dusk", "Rain", "Dawn", "Noon", "Night", "Morning", "Fog",
  "Twilight", "Evening", "Afternoon", "Snow", "Harbor", "Lantern", "Midnight",
] as const;

/**
 * A name from the blend's accords, strongest first. `random` is injectable
 * so the name is testable; the default is `Math.random`.
 */
export function generateBlendName(accords: readonly AccordKey[], random: () => number = Math.random): string {
  const lead = accords[0] ?? "neutral";
  const source = random() < 0.5 ? lead : (accords[1] ?? lead);
  const words = ACCORD_WORDS[source];
  const first = words[Math.floor(random() * words.length)];
  const second = TIME_WORDS[Math.floor(random() * TIME_WORDS.length)];
  return `${first} ${second}`;
}
