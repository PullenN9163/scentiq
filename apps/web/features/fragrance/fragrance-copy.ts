import type { CollectionItem, FragranceDetail, NoteStage, WearLogEntry } from "@/types/api";

const DAY_MS = 24 * 60 * 60 * 1000;

export const STAGE_LABELS: { key: NoteStage; label: string }[] = [
  { key: "top", label: "Top" },
  { key: "middle", label: "Heart" },
  { key: "base", label: "Base" },
  { key: "general", label: "Notes" },
];

/** Notes grouped by stage, leaving out empty stages. */
export function notesByStage(notes: FragranceDetail["notes"]): { label: string; notes: string[] }[] {
  return STAGE_LABELS.map(({ key, label }) => ({ label, notes: notes.filter((note) => note.stage === key).map((note) => note.name) })).filter((group) => group.notes.length > 0);
}

function daysAgo(instant: string, now: Date): number {
  return Math.max(0, Math.floor((now.getTime() - new Date(instant).getTime()) / DAY_MS));
}

/** The best single fact about the member and this fragrance, or null. */
export function personalLine(fragrance: FragranceDetail, item: CollectionItem | null, wears: readonly WearLogEntry[], now = new Date()): string | null {
  if (wears.length > 0) {
    const latest = [...wears].sort((a, b) => b.worn_at.localeCompare(a.worn_at))[0];
    const days = daysAgo(latest.worn_at, now);
    const when = days === 0 ? "last today" : days === 1 ? "last yesterday" : `last ${days} days ago`;
    return `Worn ${wears.length} ${wears.length === 1 ? "time" : "times"}, ${when}.`;
  }
  if (item?.status === "owned") return "On your shelf, not worn yet.";
  if (item?.status === "wishlist") return "On your wishlist.";
  if (item?.status === "finished") return "Finished.";
  const facts = [fragrance.concentration, fragrance.release_year ? String(fragrance.release_year) : null].filter(Boolean);
  return facts.length > 0 ? facts.join(" · ") : null;
}

/** Wears per week for the last `weeks` weeks, oldest first. */
export function weeklyWears(wears: readonly WearLogEntry[], weeks = 12, now = new Date()): number[] {
  const buckets = Array.from({ length: weeks }, () => 0);
  for (const wear of wears) {
    const age = Math.floor((now.getTime() - new Date(wear.worn_at).getTime()) / (7 * DAY_MS));
    if (age >= 0 && age < weeks) buckets[weeks - 1 - age] += 1;
  }
  return buckets;
}
