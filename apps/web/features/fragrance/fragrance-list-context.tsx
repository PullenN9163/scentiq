"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type ListContext = { ids: string[]; setIds: (ids: string[]) => void };

const FragranceListContext = createContext<ListContext>({ ids: [], setIds: () => {} });

/**
 * Holds the ordered list of fragrance ids the member is browsing, so the
 * fragrance sheet can step to the previous and next one. Lives in the shell,
 * which persists across navigation.
 */
export function FragranceListProvider({ children }: { children: ReactNode }) {
  const [ids, setIds] = useState<string[]>([]);
  return <FragranceListContext value={{ ids, setIds }}>{children}</FragranceListContext>;
}

/** Register the ids a page shows, in display order. */
export function useRegisterFragranceList(ids: readonly string[]) {
  const { setIds } = useContext(FragranceListContext);
  const key = ids.join(",");
  useEffect(() => {
    setIds(key ? key.split(",") : []);
  }, [key, setIds]);
}

/** Previous and next ids around `id`, or nulls when it was opened from a single item. */
export function useFragranceNeighbours(id: string): { previous: string | null; next: string | null; position: number; total: number } {
  const { ids } = useContext(FragranceListContext);
  const index = ids.indexOf(id);
  if (index < 0 || ids.length < 2) return { previous: null, next: null, position: 0, total: 0 };
  return { previous: ids[index - 1] ?? null, next: ids[index + 1] ?? null, position: index + 1, total: ids.length };
}
