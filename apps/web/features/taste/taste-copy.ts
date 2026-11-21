import type { CollectionInsights, CollectionItem, WeightedSlice } from "@/types/api";

/** "Mostly woody and fresh." from the accord shares, largest first. */
export function tasteStatement(accords: readonly WeightedSlice[]): string | null {
  const ranked = [...accords].filter((accord) => accord.share > 0).sort((a, b) => b.share - a.share);
  if (ranked.length === 0) return null;
  if (ranked.length === 1) return `Mostly ${ranked[0].label.toLowerCase()}.`;
  return `Mostly ${ranked[0].label.toLowerCase()} and ${ranked[1].label.toLowerCase()}.`;
}

/** "26 fragrances · 42 wears · 12 in the last 30 days" */
export function tasteCaption(insights: CollectionInsights): string {
  const parts = [`${insights.total_items} ${insights.total_items === 1 ? "fragrance" : "fragrances"}`];
  if (insights.total_wears > 0) parts.push(`${insights.total_wears} ${insights.total_wears === 1 ? "wear" : "wears"}`);
  if (insights.wears_last_30_days > 0) parts.push(`${insights.wears_last_30_days} in the last 30 days`);
  return parts.join(" · ");
}

/** Index the collection by fragrance id, for plates on insight entries. */
export function byFragranceId(items: readonly CollectionItem[]): Map<string, CollectionItem> {
  return new Map(items.map((item) => [item.fragrance.id, item]));
}

/** "Not worn in 60 days", "Not worn yet". */
export function notWornLine(lastWornAt: string | null, now = new Date()): string {
  if (!lastWornAt) return "Not worn yet";
  const days = Math.max(0, Math.floor((now.getTime() - new Date(lastWornAt).getTime()) / 86_400_000));
  return days === 0 ? "Worn today" : `Not worn in ${days} ${days === 1 ? "day" : "days"}`;
}

/** The season with the smallest share, which is marked thin. */
export function thinnestSeason(seasons: readonly WeightedSlice[]): string | null {
  if (seasons.length < 2) return null;
  return [...seasons].sort((a, b) => a.share - b.share)[0].label;
}

/** "Thin for summer and winter." */
export function seasonGapSentence(gaps: readonly string[] | undefined): string | null {
  const list = (gaps ?? []).map((gap) => gap.trim().toLowerCase()).filter(Boolean);
  if (list.length === 0) return null;
  const joined = list.length === 1 ? list[0] : `${list.slice(0, -1).join(", ")} and ${list[list.length - 1]}`;
  return `Your shelf is thin for ${joined}.`;
}

/** "share cedar and tea" */
export function sharedWords(shared: readonly string[]): string {
  const list = shared.slice(0, 3).map((accord) => accord.toLowerCase());
  if (list.length === 0) return "smell alike";
  if (list.length === 1) return `share ${list[0]}`;
  return `share ${list.slice(0, -1).join(", ")} and ${list[list.length - 1]}`;
}

/** Decimal string money without assuming a currency symbol. */
export function money(value: string | null | undefined): string | null {
  if (!value) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString("en-GB", { minimumFractionDigits: number % 1 ? 2 : 0, maximumFractionDigits: 2 }) : null;
}
