import assert from "node:assert/strict";
import { percentile, summarize } from "./discovery-benchmark-core.mjs";
assert.equal(percentile([4, 1, 3, 2], 0.5), 2);
assert.equal(percentile([4, 1, 3, 2], 0.75), 3);
assert.equal(percentile([4, 1, 3, 2], 0.95), 4);
assert.equal(percentile([], 0.95), null);
const summary = summarize([
  { durationMs: 4, ok: true, size: 25, cacheControl: "private, no-store" },
  { durationMs: 1, ok: true, size: 24, cacheControl: "private, no-store" },
  { durationMs: 3, ok: false, size: null, cacheControl: null },
  { durationMs: 2, ok: true, size: 26, cacheControl: "private, no-store" },
]);
assert.equal(summary.errors, 1);
assert.equal(summary.errorRate, 0.25);
assert.equal(summary.meetsOnePercentErrorTarget, false);
assert.deepEqual(summary.requestListSize, { samples: 3, median: 25 });
console.log("Benchmark percentile and error-rate checks passed.");
