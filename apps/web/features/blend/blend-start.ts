import type { CollectionItem } from "@/types/api";
import type { SavedLayeringStack } from "@/types/layering";

import { toGoal, toMode } from "./blend-copy";
import { MAX_BOTTLES, type BlendSnapshot, type BlendStart } from "./blend-state";

/** The query parameters the studio understands (the assistant links to these). */
export type BlendQuery = { a?: string; stack?: string; saved?: string; mode?: string; goal?: string };

/** Where the studio starts; `evaluate` means the server should read the stack first. */
export type BlendLoad = { start: BlendStart; evaluate: boolean };

/** Owned bottles, most rated first, unrated last, then by name. */
export function shelfOrder(owned: CollectionItem[]): CollectionItem[] {
  return [...owned].sort((a, b) => (b.user_rating ?? -1) - (a.user_rating ?? -1) || a.fragrance.name.localeCompare(b.fragrance.name));
}

/**
 * Resolves the query to a starting flask. `saved` wins, then `stack`, then
 * `a`. Only bottles the member owns can start in the flask.
 */
export function blendStartFromQuery(query: BlendQuery, owned: CollectionItem[], saved: SavedLayeringStack[]): BlendLoad {
  const ownedIds = new Set(owned.map((item) => item.fragrance.id));
  const mode = toMode(query.mode);
  const goal = toGoal(query.goal);

  if (query.saved) {
    const stack = saved.find((entry) => entry.id === query.saved);
    if (stack) {
      const ordered = [...stack.suggestion.items]
        .sort((a, b) => a.application_order - b.application_order)
        .map((item) => item.fragrance.id);
      const ids = ordered.filter((id) => ownedIds.has(id)).slice(0, MAX_BOTTLES);
      const complete = ids.length === ordered.length;
      return {
        start: { ids, mode: stack.suggestion.mode, goal: stack.suggestion.goal ?? null, savedId: stack.id, suggestion: complete ? stack.suggestion : null },
        evaluate: !complete && ids.length >= 2,
      };
    }
  }

  if (query.stack) {
    const ids = query.stack.split(",").map((id) => id.trim()).filter(Boolean);
    const valid = ids.length >= 2 && ids.length <= MAX_BOTTLES && new Set(ids).size === ids.length && ids.every((id) => ownedIds.has(id));
    if (valid) return { start: { ids, mode, goal, savedId: null, suggestion: null }, evaluate: true };
  }

  if (query.a && ownedIds.has(query.a)) {
    return { start: { ids: [query.a], mode, goal, savedId: null, suggestion: null }, evaluate: false };
  }

  return { start: { ids: [], mode, goal, savedId: null, suggestion: null }, evaluate: false };
}

/** The snapshot a saved blend was made from, for matching the flask to it. */
export function snapshotOfSaved(entry: SavedLayeringStack): BlendSnapshot {
  return {
    ids: [...entry.suggestion.items].sort((a, b) => a.application_order - b.application_order).map((item) => item.fragrance.id),
    mode: entry.suggestion.mode,
    goal: entry.suggestion.goal ?? null,
  };
}
