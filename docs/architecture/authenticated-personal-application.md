# Authenticated Personal Application

## Status

Implemented September 23, 2026. Targets the existing Azure development topology as a private beta, not a production environment.

## Objective

Turn the ScentIQ frontend shell into an authenticated personal application. Each signed-in member gets a durable profile, preferences, collection, wear history and private custom fragrances, while the visual design and the existing FastAPI, PostgreSQL and Azure foundation are preserved.

## Scope

This milestone delivers:

- invite-only Clerk authentication, with the app shell protected and the landing page, sign-in routes, webhook and status probe public;
- an internal identity mapping from provider subjects to ScentIQ user identifiers, provisioned on first authenticated request;
- persisted profiles, preferences, collections, wear logs and private custom fragrances;
- collection insights computed from persisted data;
- a same-origin Next.js backend-for-frontend over the internally hosted FastAPI service;
- a two-phase account deletion flow driven by a signed provider webhook, with scheduled reconciliation;
- clearly labelled previews for weekly planning, layering, discovery and the agent; and
- a generated API contract that continuous integration holds the web application to.

Excluded: external fragrance datasets, image uploads, live weather and calendar connections, notifications, recommendation scoring and language-model agent calls.

## Identity and the service boundary

The browser communicates only with Next.js. FastAPI keeps internal ingress and is never publicly routable.

1. Clerk authenticates the member in the browser.
2. Next.js reads the session token on the server and calls FastAPI over `API_INTERNAL_URL`.
3. FastAPI verifies the token's signature, issuer, audience, authorized party and expiry against the provider's JWKS.
4. FastAPI resolves the token's subject to an internal user, creating one on first contact.

Authentication fails closed. When `CLERK_ISSUER` is absent, protected endpoints return `503 authentication_unavailable` rather than allowing the request.

### The email claim

`users.email` is `NOT NULL`, and requests never carry identity, so just-in-time provisioning has no source for a new member's email other than the verified token. **The ScentIQ Clerk JWT template must therefore include an `email` claim.** A token without one is rejected. Email remains read-only in the product; the provider owns it.

### Provisioning under concurrency

Two simultaneous first requests race for the same subject. The unique constraint on `(provider, subject)` decides the winner; the loser rolls back and re-reads the committed row. The identity mapping is committed as soon as it is created, so it survives a later failure in the same request.

## Data ownership

Catalog rows carry a nullable `owner_user_id`:

- a `NULL` owner marks a **shared curated** row, readable by everyone;
- a non-null owner marks a **private custom** row, visible only to its creator.

Global catalog uniqueness was replaced with partial unique indexes so the two kinds can coexist:

| Index | Applies when |
| --- | --- |
| `uq_brands_shared_name`, `uq_brands_shared_slug` | `owner_user_id IS NULL` |
| `uq_brands_custom_name` on `(owner_user_id, name)` | `owner_user_id IS NOT NULL` |
| `uq_fragrances_shared_identity` on `(brand_id, name, concentration)` | `owner_user_id IS NULL` |
| `uq_fragrances_custom_identity` on `(owner_user_id, brand_id, name, concentration)` | `owner_user_id IS NOT NULL` |

Two members can therefore both record a private "Indie House" entry, while the curated catalog stays globally unique.

Every repository method takes an authenticated user identifier and includes an ownership predicate. A private row belonging to another member returns `404`, not `403`: existence itself must not leak.

## Deletion behaviour

Before this milestone only `user_preferences.user_id` cascaded. Every user-scoped foreign key now carries `ON DELETE CASCADE`, covering collection items, wear logs, wear feedback, wishlists, calendar events, weather snapshots, recommendations, layering logs, the identity mapping and the ownership columns on `brands` and `fragrances`. Without this, removing a member whose own custom fragrance sat in their collection would raise a foreign-key violation.

Custom catalog rows are deleted explicitly before the member row so the ordering is visible in the code rather than implied, and so a curated row can never be caught by the cascade.

## Account deletion flow

Deletion is deliberately two-phase, so a partial failure is recoverable rather than stranding an account.

1. `POST /api/v1/me/deletion` marks the member `deletion_pending`. Every endpoint except the rollback then refuses the account.
2. Next.js deletes the Clerk identity. If that call fails, `POST /api/v1/me/deletion/cancel` restores `active`.
3. Clerk sends a signed `user.deleted` webhook. The public Next.js route verifies the Svix signature, normalises the event and forwards it to the internal FastAPI endpoint with a dedicated service credential.
4. FastAPI removes the member and everything they own in one transaction, keyed on the provider event id so replays are no-ops.

The rollback endpoint is the one place a `deletion_pending` account is allowed to authenticate — otherwise the member marked in step 1 could never reach step 2's recovery.

`python -m scentiq_api.reconcile_deletions` purges accounts still pending after a grace period, covering a webhook that never arrived.

## API contract

All endpoints are authenticated and live under `/api/v1`:

| Method | Path |
| --- | --- |
| GET, PATCH | `/me` |
| PATCH | `/me/preferences` |
| POST | `/me/deletion`, `/me/deletion/cancel` |
| GET, POST | `/fragrances` |
| GET | `/fragrances/{id}` |
| GET, POST | `/collection` |
| PATCH | `/collection/{id}` |
| GET, POST | `/wear-logs` |
| GET | `/insights/collection` |

`POST /api/v1/internal/identity-events` is excluded from the public schema and authenticates with the service credential alone.

Contract rules:

- identity always comes from the verified token; no request accepts a `user_id`, and unknown fields are rejected;
- identifiers are UUIDs and timestamps are ISO-8601 with an explicit offset;
- money is serialised as a decimal string (`"129.50"`), never a float, so no precision is lost;
- enumerated values are lower-case and match the database check constraints exactly;
- ratings are whole numbers from 1 to 5;
- a custom fragrance requires brand, name and concentration; descriptive and classification metadata is optional;
- collection items are marked `finished` or `sold` rather than deleted, preserving wear history; and
- errors use `{code, message, field_errors?, request_id}` with stable status semantics.

`apps/api/openapi.json` is generated by `pnpm contracts:openapi` and is the source for the web application's types. Continuous integration regenerates it and fails on any difference.

## Frontend composition

A single server-only client (`lib/server/api-client.ts`) reaches FastAPI. Importing it from a Client Component is a build error, which is what keeps the session token on the server. Reads are tagged so a mutation can invalidate exactly the affected resources.

Mutations are Server Actions returning a common result shape that carries field errors and echoes the submitted values, so a failed form re-renders with the member's input intact rather than blanking it.

Connected to persisted data: Collection, Fragrance Detail, Settings, Insights, and the Today totals and recent wears.

Still previews, and labelled as such on screen: weekly planning, layering, discovery, the agent, and the weather, event and recommendation cards on Today. No preview action claims to have been saved.

Insights report how much of a collection each breakdown covers. Custom fragrances normally carry no accord, season or occasion data, so a breakdown that silently omitted them would misrepresent the collection.

## Configuration

Clerk keys, the webhook secret, token-validation settings and the internal service credential are Key Vault-backed Container App secrets. `.env.example` documents them as empty placeholders; no real value is committed.

| Variable | Used by |
| --- | --- |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Web (public by design) |
| `CLERK_SECRET_KEY` | Web (server only) |
| `CLERK_WEBHOOK_SECRET` | Web webhook route |
| `CLERK_ISSUER`, `CLERK_JWKS_URL`, `CLERK_AUDIENCE`, `CLERK_AUTHORIZED_PARTIES` | API token verification |
| `INTERNAL_SERVICE_TOKEN` | Web webhook route and API internal endpoint |

## Verification

- **Token verification** — valid, expired, wrong issuer, wrong audience, unknown signing key, unsigned `alg=none`, missing email claim, unexpected authorized party, and key rotation.
- **Authorization** — cross-member reads and writes against the catalog, collection, wear logs and insights return no private data, and an unknown identifier is indistinguishable from someone else's.
- **Domain** — catalog search and visibility, custom-fragrance validation and duplicate refusal, collection lifecycle updates, wear-log filters, and insight arithmetic with both complete and incomplete metadata.
- **Deletion** — pending marking and its idempotence, replayed webhooks, rollback, cascade correctness, curated-catalog survival, and reconciliation recovery.
- **Migrations** — table set, downgrade and re-upgrade, model drift, seed idempotence, partial uniqueness, and that every user-scoped foreign key cascades.

Tests that depend on PostgreSQL behaviour live under `apps/api/tests/integration` and are skipped unless `DATABASE_URL` is set. Two guarantees can only be verified there: partial unique indexes, which SQLite expresses as full unique indexes, and the cascade rules as PostgreSQL enforces them.

## Deployment sequence

1. Apply migrations.
2. Deploy the API revision.
3. Deploy the web revision.

Prior healthy revisions are retained for rollback. The API keeps internal ingress throughout.
