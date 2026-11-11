# Performance rollout and database co-location

This runbook controls the rollout of ScentIQ's page-shaped reads, recommendation snapshots, and optional PostgreSQL move from North Central US to East US. It is designed to keep the existing synchronous APIs available at every stage.

## Service-level objectives

Use the production-like authenticated 24-hour verification procedure below before calling a rollout stable. A short development check or an old snapshot test does not establish a live 24-hour result.

| Signal | Target | Rollback threshold |
| --- | ---: | ---: |
| Warm app page load | below 1.5 seconds | above 2 seconds for 15 minutes |
| Discovery search API p95 | at most 500 ms after the 200 ms input debounce | above 750 ms for 15 minutes |
| Snapshot recommendation API p75 | below 500 ms | above 1 second for 15 minutes |
| API p95 | below 2 seconds | alert already fires above 2 seconds for 15 minutes |
| Recommendation freshness | below 5 minutes | oldest pending job above 10 minutes |
| HTTP failures | below 1% | above 5% for 15 minutes |

On supported mobile devices, measure field or representative lab Core Web Vitals separately: LCP at most 2.5 seconds, INP at most 200 ms, and CLS at most 0.1. Browser navigation timing includes rendering, images, and client work; API `Server-Timing` and Application Insights request duration measure server work. Report them as separate series. Do not infer mobile LCP or interaction latency from an API load test.

Use Application Insights `AppRequests` to compare these paths separately:

- `/api/v1/page-data/dashboard`
- `/api/v1/page-data/layering`
- `/api/v1/page-data/week`
- `/api/v1/page-data/fragrances/{id}`
- `/api/v1/recommendations`

Every API response includes `Server-Timing: app;dur=...`, which separates API work from browser/network time. Authenticated responses remain `private, no-store`; never introduce shared caching for member page data.

Run the private same-origin benchmark with `node scripts/discovery-benchmark.mjs --samples 100`. Set `SCENTIQ_BENCHMARK_BASE_URL`, the matching `SCENTIQ_BENCHMARK_ALLOWED_ORIGIN`, and either `SCENTIQ_BENCHMARK_BEARER_TOKEN` or `SCENTIQ_BENCHMARK_COOKIE` in the shell environment. It sends GETs only to `/api/discover/search` and `/api/discover/feed`, rotates four fixed search terms or feed modes, warms each route, and records p50/p75/p95 and errors for 1, 5, and 10 concurrent requests. Select one run with `--scenario catalog-search --concurrency 5` if a short-lived session must be refreshed between runs. Results go to the private `ScentIQ-AI/artifacts` directory by default. Keep credentials out of command arguments, files, and captured output. This measures the same-origin Next route and its upstream work; it is not a browser/device result. For page and mobile metrics, use a real signed-in browser and record device, viewport, cache state, and navigation type separately. Supply an operator-verified `SCENTIQ_BENCHMARK_CATALOG_SIZE` and `SCENTIQ_BENCHMARK_DEVICE_NOTE` only when known; otherwise the report says the catalogue size is unknown.

## Staged activation

1. Deploy the migration and API/web changes while leaving the home worker stopped. Confirm page-shaped reads and synchronous recommendation fallback work.
2. Deploy the Storage queues and scheduled hybrid bridge. Confirm an empty bridge run succeeds.
3. Start the home worker and exercise one test member. Confirm version promotion, replay handling, and stale-result rejection.
4. Observe for 24 hours. Stop the worker if poison messages appear or freshness exceeds ten minutes; request traffic continues on fallback.
5. Enable the worker for normal use only after the freshness and failure targets hold.

## 24-hour outage and recovery verification

The current offline tests exercise a 24-hour-old snapshot and confirm stale data stays marked stale while a refresh remains pending. They do not simulate a 24-hour live outage. To verify actual recovery, schedule a supervised 24-hour worker-offline window in a nonproduction environment with representative data. Keep the web/API online, stop the worker, and sample the signed-in discovery feed and recommendation response periodically. Confirm pages continue with bounded synchronous fallback, never report the old snapshot as fresh, and record no writes or data loss. Then restart one worker, observe queue age, poison count, and bridge status, and verify that a result for the current input version is promoted and the next read reports fresh within five minutes. Record the exact window, sample times, request p50/p75/p95, error rate, queue age, result version, and recovery time before claiming completion. Do not label a unit test or a short smoke test as a completed 24-hour soak.

## PostgreSQL co-location rehearsal

The current application workloads run in East US while PostgreSQL is configured in North Central US. Do not move the database on assumption alone. First capture the page-path p50/p75/p95 and database dependency duration for 24 hours. A co-location move is justified only when cross-region database time contributes at least 150 ms to p75 page requests or at least 25% of their server duration.

Rehearse in the test resource group:

1. Create a point-in-time East US restore with the guarded restore workflow in `azure-recovery.md`. Never overwrite or delete the source server.
2. Deploy a test API revision in East US against the restored database. Keep external ingress disabled.
3. Run the authenticated page-path suite against both test APIs with the same warm dataset. Record at least 100 samples per path and compare p50, p75, p95, error rate, and PostgreSQL CPU.
4. Validate migrations, row counts, identity ownership boundaries, collection mutations, job invalidation, bridge dispatch, and result promotion.
5. Estimate the steady-state server cost with Azure's current price for the same B1ms class. The move must stay inside the approved incremental budget.
6. Delete the rehearsal restore only through the guarded cleanup procedure after results are recorded.

Approve a production move only if East US improves page p75 by at least 15%, does not regress p95 or error rate, and passes the full recovery rehearsal. Schedule a maintenance window, take a final restore point, deploy the new database URL through Key Vault, and retain the old server without writes until post-cutover verification finishes.

Rollback immediately if authentication provisioning, collection writes, migration checks, or the latency/error thresholds fail. Restore the prior Key Vault database URL and Container App revision; do not attempt to repair data by copying individual rows during the incident.

## Cache and rendering checks

- Confirm dashboard, layering, week, and fragrance detail render with one API request each from the Next.js server.
- Confirm the default Discover view uses the recommendation snapshot, while filtered searches use the authoritative filtered endpoint.
- Confirm no authenticated response is stored by a browser, proxy, or CDN.
- Confirm the detail hero image is preloaded and list images use responsive `sizes` through the Next.js image optimizer.
- Review Next.js bundle output after each dependency change; do not move server-only API code into client components.
- Roll back fast discovery by setting `SCENTIQ_FAST_DISCOVERY_ENABLED=false` on the web revision; the server-rendered authoritative collection, discovery, and catalog-search reads remain available. Roll back premium styling with `SCENTIQ_PREMIUM_UI_ENABLED=false`; reduced-motion and performance rules in the base stylesheet remain active. Verify both flags on the rendered revision before closing the incident.

## Cost feasibility gate

Keep the always-available Azure design below the approved $50/month ceiling, with a forecast at or below $45/month to retain a $5 variance buffer. Reconcile all Azure services, including Container Apps, registry, storage, Key Vault, monitoring, and PostgreSQL. PostgreSQL currently relies on a free allowance; treat its expiry as an explicit cost risk and recalculate the all-in forecast using the paid server size before that allowance ends. Do not call a quota a hard cost stop: the Log Analytics daily cap is a volume control and may not prevent every billable ingestion path. Availability probes remain enabled on the public root and `/api/status`; one probe region every 15 minutes lowers schedule frequency substantially. With a 900-second probe interval, 15-minute query bins/window, and two failing evaluations, outage confirmation may take roughly 30 minutes, plus telemetry ingestion and notification delay. Validate end-to-end alert behavior with a controlled nonproduction failure before relying on this timing; record observation, alert firing, and notification times. Keep the actionable alert and check the resource's actual cost after rollout. Measure database dependency and page timings across regions for at least 24 hours before proposing a database move; include the paid target size in the budget gate.
