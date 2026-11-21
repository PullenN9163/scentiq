export function percentile(values, fraction) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.max(0, Math.ceil(fraction * sorted.length) - 1)];
}

export function summarize(results) {
  const durations = results.map((item) => item.durationMs);
  const errors = results.filter((item) => !item.ok).length;
  const sizes = results.map((item) => item.size).filter((value) => value !== null);
  return {
    samples: results.length,
    p50Ms: percentile(durations, 0.5),
    p75Ms: percentile(durations, 0.75),
    p95Ms: percentile(durations, 0.95),
    errors,
    errorRate: results.length ? errors / results.length : 0,
    meetsOnePercentErrorTarget: results.length > 0 && errors / results.length <= 0.01,
    requestListSize: sizes.length ? { samples: sizes.length, median: percentile(sizes, 0.5) } : null,
    cacheControl: results.find((item) => item.cacheControl)?.cacheControl ?? null,
  };
}
