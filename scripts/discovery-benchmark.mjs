#!/usr/bin/env node
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { summarize } from "./discovery-benchmark-core.mjs";

const args = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index];
  if (!key.startsWith("--") || !process.argv[index + 1]) throw new Error(`Invalid argument near ${key}`);
  args.set(key.slice(2), process.argv[++index]);
}
const base = process.env.SCENTIQ_BENCHMARK_BASE_URL;
const allowedOrigin = process.env.SCENTIQ_BENCHMARK_ALLOWED_ORIGIN;
if (!base || !allowedOrigin) throw new Error("Set SCENTIQ_BENCHMARK_BASE_URL and SCENTIQ_BENCHMARK_ALLOWED_ORIGIN explicitly.");
const target = new URL(base);
if (!["http:", "https:"].includes(target.protocol) || target.origin !== allowedOrigin || target.username || target.password) {
  throw new Error("Benchmark base URL must be HTTP(S), contain no credentials, and match the explicitly allowed origin.");
}
const sampleCount = Number(args.get("samples") ?? 100);
if (!Number.isInteger(sampleCount) || sampleCount < 100 || sampleCount > 5000) throw new Error("--samples must be an integer from 100 to 5000.");
const timeoutMs = Number(args.get("timeout-ms") ?? 15000);
if (!Number.isInteger(timeoutMs) || timeoutMs < 1000 || timeoutMs > 60000) throw new Error("--timeout-ms must be from 1000 to 60000.");
const scenarios = [
  { name: "catalog-search", paths: ["/api/discover/search?q=amber&limit=25&offset=0", "/api/discover/search?q=Dior&limit=25&offset=0", "/api/discover/search?q=Terre&limit=25&offset=0", "/api/discover/search?q=zz-no-match&limit=25&offset=0"] },
  { name: "discovery-feed", paths: ["/api/discover/feed?mode=balance&limit=25&offset=0", "/api/discover/feed?mode=taste&limit=25&offset=0", "/api/discover/feed?mode=explore&limit=25&offset=0", "/api/discover/feed?mode=seasonal&limit=25&offset=0"] },
];
const selectedScenario = args.get("scenario");
if (selectedScenario && !scenarios.some(({ name }) => name === selectedScenario)) throw new Error("--scenario must be catalog-search or discovery-feed.");
const selectedConcurrency = args.get("concurrency");
if (selectedConcurrency && !["1", "5", "10"].includes(selectedConcurrency)) throw new Error("--concurrency must be 1, 5, or 10.");
const auth = process.env.SCENTIQ_BENCHMARK_BEARER_TOKEN;
const cookie = process.env.SCENTIQ_BENCHMARK_COOKIE;
if (!auth && !cookie) throw new Error("Set SCENTIQ_BENCHMARK_BEARER_TOKEN or SCENTIQ_BENCHMARK_COOKIE in the environment.");
const headers = { Accept: "application/json" };
if (auth) headers.Authorization = `Bearer ${auth}`;
if (cookie) headers.Cookie = cookie;
const deviceNote = process.env.SCENTIQ_BENCHMARK_DEVICE_NOTE ?? "Node same-origin route; no browser/device rendering measured";
const parseSize = (scenario, body) => {
  try {
    const value = JSON.parse(body);
    if (scenario === "discovery-feed") return Array.isArray(value?.items) ? value.items.length : null;
    return Array.isArray(value) ? value.length : null;
  } catch { return null; }
};
async function request(scenario, requestIndex) {
  const path = scenario.paths[requestIndex % scenario.paths.length];
  const url = new URL(path, target);
  if (url.origin !== allowedOrigin || !url.pathname.startsWith("/api/discover/")) throw new Error("Refusing a request outside the permitted same-origin read routes.");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const start = performance.now();
  try {
    const response = await fetch(url, { method: "GET", headers, signal: controller.signal, redirect: "error", cache: "no-store" });
    const body = await response.text();
    let shapeValid = false;
    try {
      const parsed = JSON.parse(body);
      shapeValid = scenario.name === "catalog-search"
        ? Array.isArray(parsed)
        : Array.isArray(parsed?.items) && typeof parsed?.refresh_status === "string";
    } catch { /* A successful HTTP response with malformed JSON is still a failed sample. */ }
    const ok = response.ok && shapeValid;
    return { durationMs: performance.now() - start, status: response.status, ok, size: parseSize(scenario.name, body), cacheControl: response.headers.get("cache-control"), error: ok ? null : response.ok ? "invalid_response_shape" : `http_${response.status}` };
  } catch (error) {
    return { durationMs: performance.now() - start, status: null, ok: false, size: null, cacheControl: null, error: error?.name === "AbortError" ? "timeout" : "network_error" };
  } finally { clearTimeout(timer); }
}
async function runLoad(scenario, count, concurrency) {
  const results = new Array(count);
  let cursor = 0;
  await Promise.all(Array.from({ length: Math.min(concurrency, count) }, async () => {
    while (true) {
      const index = cursor++;
      if (index >= count) return;
      results[index] = await request(scenario, index);
    }
  }));
  return results;
}
const catalogSizeInput = process.env.SCENTIQ_BENCHMARK_CATALOG_SIZE;
const catalogSize = catalogSizeInput && /^\d+$/.test(catalogSizeInput) ? Number(catalogSizeInput) : null;
const output = { generatedAt: new Date().toISOString(), origin: target.origin, scenarios: [], notes: { samplesPerConcurrency: sampleCount, warmupRequestsPerScenario: 5, catalogSize, catalogSizeSource: catalogSize === null ? "not supplied" : "operator supplied; verify source and timestamp", device: deviceNote, tokenHandling: "credentials read from process environment; never included in output" } };
for (const scenario of scenarios.filter(({ name }) => !selectedScenario || name === selectedScenario)) {
  const warmup = await runLoad(scenario, 5, 1);
  const levels = [];
  for (const concurrency of (selectedConcurrency ? [Number(selectedConcurrency)] : [1, 5, 10])) {
    const results = await runLoad(scenario, sampleCount, concurrency);
    levels.push({
      concurrency,
      ...summarize(results),
    });
  }
  output.scenarios.push({ name: scenario.name, method: "GET", requestMix: scenario.paths, warmupErrors: warmup.filter((item) => !item.ok).length, levels });
}
const outputDirectory = args.has("output-dir") ? resolve(args.get("output-dir")) : resolve(dirname(fileURLToPath(import.meta.url)), "../../artifacts");
await mkdir(outputDirectory, { recursive: true });
const outputPath = resolve(outputDirectory, args.get("output") ?? `discovery-benchmark-${new Date().toISOString().replaceAll(":", "-")}.json`);
if (!outputPath.startsWith(`${outputDirectory}/`) && !outputPath.startsWith(`${outputDirectory}\\`)) throw new Error("Output path must remain inside the selected private output directory.");
await writeFile(outputPath, `${JSON.stringify(output, null, 2)}\n`, { flag: "wx" });
console.log(JSON.stringify({ outputPath, origin: output.origin, scenarios: output.scenarios.map(({ name, levels }) => ({ name, levels })) }, null, 2));
