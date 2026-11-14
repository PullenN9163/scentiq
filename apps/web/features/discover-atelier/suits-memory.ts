"use client";

/**
 * Discovery scores travel to the fragrance sheet as words. The sheet is a
 * separate route, so the last scores shown on Discover are remembered here
 * for the session, keyed by fragrance id.
 */
const memory = new Map<string, string[]>();

export function rememberSuits(fragranceId: string, words: string[]) {
  if (words.length) memory.set(fragranceId, words);
}

export function suitsFor(fragranceId: string): string[] {
  return memory.get(fragranceId) ?? [];
}
