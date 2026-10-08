# Performance rollout and database co-location

This runbook controls the rollout of ScentIQ's page-shaped reads, recommendation snapshots, and optional PostgreSQL move from North Central US to East US. It is designed to keep the existing synchronous APIs available at every stage.

## Service-level objectives

Measure production-like authenticated traffic for at least 24 hours before and after each change.

| Signal | Target | Rollback threshold |
| --- | ---: | ---: |
| App page p75 | below 1.5 seconds | above 2 seconds for 15 minutes |
| Snapshot recommendation API p75 | below 500 ms | above 1 second for 15 minutes |
| API p95 | below 2 seconds | alert already fires above 2 seconds for 15 minutes |
| Recommendation freshness | below 5 minutes | oldest pending job above 10 minutes |
| HTTP failures | below 1% | above 5% for 15 minutes |

Use Application Insights `AppRequests` to compare these paths separately:

- `/api/v1/page-data/dashboard`
- `/api/v1/page-data/layering`
- `/api/v1/page-data/week`
- `/api/v1/page-data/fragrances/{id}`
- `/api/v1/recommendations`

Every API response includes `Server-Timing: app;dur=...`, which separates API work from browser/network time. Authenticated responses remain `private, no-store`; never introduce shared caching for member page data.

## Staged activation

1. Deploy the migration and API/web changes while leaving the home worker stopped. Confirm page-shaped reads and synchronous recommendation fallback work.
2. Deploy the Storage queues and scheduled hybrid bridge. Confirm an empty bridge run succeeds.
3. Start the home worker and exercise one test member. Confirm version promotion, replay handling, and stale-result rejection.
4. Observe for 24 hours. Stop the worker if poison messages appear or freshness exceeds ten minutes; request traffic continues on fallback.
5. Enable the worker for normal use only after the freshness and failure targets hold.

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
