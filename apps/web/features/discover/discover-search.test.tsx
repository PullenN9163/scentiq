import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// The Discover route renders this component from its server-side loading state.
// Without the client directive Next rejects the form's submit handler and the whole
// route answers 500 while it loads.
describe("DiscoverSearch", () => {
  it("is a client component so the loading route can render it", () => {
    const source = readFileSync(join(__dirname, "discover-search.tsx"), "utf8");
    expect(source.trimStart().startsWith('"use client"')).toBe(true);
  });
});
