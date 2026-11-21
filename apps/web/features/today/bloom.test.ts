import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { claimDailyBloom, localDayKey } from "./bloom";

/** A minimal in-memory Storage, so the test does not depend on the environment's storage. */
function memoryStorage() {
  const items = new Map<string, string>();
  return {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => { items.set(key, value); },
    removeItem: (key: string) => { items.delete(key); },
    clear: () => items.clear(),
  };
}

beforeEach(() => {
  vi.stubGlobal("localStorage", memoryStorage());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

it("formats the local day as YYYY-MM-DD", () => {
  expect(localDayKey(new Date(2026, 0, 5, 9, 30))).toBe("2026-01-05");
  expect(localDayKey(new Date(2026, 10, 14))).toBe("2026-11-14");
});

it("claims the bloom once per day", () => {
  expect(claimDailyBloom("2026-11-14")).toBe(true);
  expect(claimDailyBloom("2026-11-14")).toBe(false);
  expect(claimDailyBloom("2026-11-15")).toBe(true);
});
