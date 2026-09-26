# Authenticated Personal Application

## Status

Implemented September 23, 2026, extended September 25, 2026 with the source-backed shared catalog, September 27, 2026 with live weather, and September 28, 2026 with Google and Outlook calendar connections. Targets the existing Azure development topology as a private beta, not a production environment.

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
- live catalog discovery and collection-based layering, with weekly planning and the agent retaining clearly labelled weather/calendar preview inputs; and
- a generated API contract that continuous integration holds the web application to.

Excluded: image uploads, notifications and language-model agent calls. Live weather and calendar connections were added afterwards; see [Weather](#weather) and [Calendar connections](#calendar-connections). The shared catalog is built from external source listings; source provenance and licensing constraints remain explicit product boundaries.

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

- a `NULL` owner marks a **shared source-backed** row, readable by everyone;
- a non-null owner marks a **private custom** row, visible only to its creator.

Global catalog uniqueness was replaced with partial unique indexes so the two kinds can coexist:

| Index | Applies when |
| --- | --- |
| `uq_brands_shared_name`, `uq_brands_shared_slug` | `owner_user_id IS NULL` |
| `uq_brands_custom_name` on `(owner_user_id, name)` | `owner_user_id IS NOT NULL` |
| `uq_fragrances_shared_identity` on `(brand_id, lower(name), concentration, release_year, gender)` with `NULLS NOT DISTINCT` | `owner_user_id IS NULL` |
| `uq_fragrances_custom_identity` on `(owner_user_id, brand_id, name, concentration)` | `owner_user_id IS NOT NULL` |

Two members can therefore both record a private "Indie House" entry, while the shared catalog retains a null-safe uniqueness backstop. Stable source mappings, rather than display names, are the primary catalog identity.

### Shared catalog provenance

Every accepted source record has one unique `(source, source_record_id)` mapping to a canonical fragrance. Deterministic match and survivorship rules merge compatible records while ambiguous matches remain in an operator review report. Imports write only shared rows, retain disappeared records, replace only imported child relationships, and use stable identifiers so collection references do not churn on refresh.

The catalog includes Fragrantica data via the Kaggle `ledecanteur/fragrantica-perfumes` corpus under CC BY-NC-SA 4.0, plus Parfumo, Luckyscent and related Fragrantica scrape listings whose licensing must be resolved before commercial use. Raw payloads are not stored in PostgreSQL; source URLs, raw source identity, per-field origin and import-run hashes provide the audit trail.

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
| GET | `/discover` |
| GET | `/layering/suggestions` |
| GET, POST | `/collection` |
| PATCH | `/collection/{id}` |
| GET, POST | `/wear-logs` |
| GET | `/insights/collection` |
| GET | `/weather/forecast` |
| GET | `/weather/places` |
| GET | `/calendar/providers`, `/calendar/connections` |
| POST | `/calendar/connections/{provider}/authorize`, `/calendar/connections/{provider}/callback` |
| PATCH | `/calendar/connections/{id}/sources/{source_id}` |
| POST | `/calendar/connections/{id}/sync` |
| DELETE | `/calendar/connections/{id}` |
| GET | `/calendar/events` |
| PATCH | `/calendar/events/{id}` |

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

Connected to persisted data: Catalog Search, Discover, Layering, Collection, Fragrance Detail, Settings, Insights, and the Today totals and recent wears.

Connected to live weather and calendars: the Today weather and events cards, the Settings location and calendar connections, My Week, and the agent's "what should I wear today" answer. My Week plans the member's next seven local days. Each day's ranking uses the season, the forecast high (below 20 °C counts as cool), whether a timed event starts at 17:00 or later (evening), and the day's leading event occasion. Formal outranks date, party, dinner, work, travel, gym and casual. Each input is optional: a missing forecast or calendar is explained on screen and the day is still planned from what remains.

Still previews, and labelled as such on screen: the Today recommendation card and notification settings. Fragrance choices in those experiences come only from the member's persisted collection. No preview action claims to have been saved.

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
| `WEATHER_API_BASE_URL`, `GEOCODING_API_BASE_URL` | API; blank uses Open-Meteo's free endpoints |
| `OPEN_METEO_API_KEY` | API; optional, for Open-Meteo's commercial plan |
| `PUBLIC_APP_URL` | API; the web origin OAuth providers redirect back to |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | API |
| `MICROSOFT_OAUTH_CLIENT_ID`, `MICROSOFT_OAUTH_CLIENT_SECRET` | API (Outlook) |
| `INTEGRATION_TOKEN_ENCRYPTION_KEY`, `INTEGRATION_TOKEN_PREVIOUS_KEYS` | API; seal stored refresh tokens |

## Weather

Forecasts come from [Open-Meteo](https://open-meteo.com/) through the API; the browser never calls the provider.

- **Location resolution.** Saving a new `location` preference geocodes it and stores the resolved label, coordinates and IANA timezone beside it. A place that matches nothing is refused with a `location_not_found` field error, leaving the saved preferences untouched. If the provider is unreachable the location is saved unresolved and resolved by the next forecast request.
- **Qualified names.** Open-Meteo matches bare place names only, so `Leeds, UK` is searched as `Leeds` and the qualifier ranks results by country, country code or region.
- **Caching.** `GET /weather/forecast` returns seven daily forecasts from the member's local today. Days are stored in `weather_snapshots` (one row per member per local date, keyed at midnight UTC) and served for 60 minutes before the provider is asked again. Past days are kept as a record of the weather on days a member wore something.
- **Failure.** With a cached forecast and an unreachable provider the response carries `stale: true`. With nothing cached it is `503 weather_unavailable`; no saved location is `409 location_required`, and an unresolvable one is `409 location_unresolved`. Today renders each of these as a state of the weather card rather than failing the page.
- **Units.** Temperatures are always Celsius on the wire. The member's `temperature_unit` preference (default Fahrenheit) is applied only for display.
- **Licensing.** The free tier is for non-commercial use. The commercial plan needs only configuration: the `customer-*` hosts and `OPEN_METEO_API_KEY`.

## Calendar connections

Members connect Google and Outlook (Microsoft Graph) calendars from Settings. Both providers implement one `CalendarProvider` contract, so the flow, sync and classification below are shared. ScentIQ runs its own OAuth flow, separate from Clerk sign-in, so any member can connect any account. Setup and operations are in the [calendar and weather runbook](../runbooks/calendar-and-weather.md).

**The flow.** The browser only ever visits Next.js and the provider.

1. **Start.** `GET /integrations/calendar/{provider}/start` is a session-protected route handler. It asks FastAPI for a consent URL. FastAPI records a single-use state and a PKCE verifier (S256) bound to the member for 10 minutes, and stores only the state's SHA-256 hash.
2. **Callback.** The provider redirects to `GET /integrations/calendar/{provider}/callback`. The route forwards the code and state to FastAPI and redirects to Settings with a notice code. Provider errors are never rendered.
3. **State check.** FastAPI checks that the state belongs to this member, provider and window. It deletes and **commits** the state before exchanging the code, so a state cannot be replayed even when the exchange fails.
4. **Grant storage.** Only the refresh token is stored, sealed with AES-256-GCM. The associated data binds each ciphertext to its member and provider, and a key-id prefix supports rotation. Access tokens live only for the request.
5. **Reconnect.** Connecting the same account again replaces the grant and keeps the member's calendar choices.

**Sync.** Sync is on demand; there is no scheduler.

- Reading events syncs any active connection not attempted in the last 15 minutes. It locks the connection row with `FOR UPDATE SKIP LOCKED`, so concurrent readers serve stored events instead of syncing twice.
- Each sync covers the window from yesterday to 21 days ahead for the calendars the member has ticked. Recurring events are expanded by the provider.
- Events are upserted by `(calendar, provider event id)`. Anything the provider no longer returns in the window is deleted. A member's choice to hide an event survives a re-sync.
- A rotated refresh token is saved in the same transaction.
- Failures:
  - `invalid_grant` or a `401` marks the connection `reauth_required`.
  - An outage records `last_error_code` and keeps serving stored events.

**Privacy.** Events keep only the title, start, end, the all-day flag, the location and a derived occasion and formality. Descriptions, attendees and meeting links are never stored. All-day events are stored at midnight UTC of their dates and compared by date on screen. Connections, calendars, events and pending states cascade on member deletion.

**Classification.** A deterministic keyword classifier maps each title to the existing occasion values and a formality. For example, "Team dinner" becomes dinner and smart, and "Sam's wedding drinks" becomes formal. Planning consumes this.

## Verification

- **Token verification** — valid, expired, wrong issuer, wrong audience, unknown signing key, unsigned `alg=none`, missing email claim, unexpected authorized party, and key rotation.
- **Authorization** — cross-member reads and writes against the catalog, collection, wear logs and insights return no private data, and an unknown identifier is indistinguishable from someone else's.
- **Domain** — catalog search and visibility, custom-fragrance validation and duplicate refusal, collection lifecycle updates, wear-log filters, and insight arithmetic with both complete and incomplete metadata.
- **Deletion** — pending marking and its idempotence, replayed webhooks, rollback, cascade correctness, curated-catalog survival, and reconciliation recovery.
- **Migrations** — table set, downgrade and re-upgrade, model drift, seed idempotence, partial uniqueness, and that every user-scoped foreign key cascades.

Tests that depend on PostgreSQL behaviour live under `apps/api/tests/integration` and are skipped unless `DATABASE_URL` is set. Two guarantees can only be verified there: partial unique indexes, which SQLite expresses as full unique indexes, and the cascade rules as PostgreSQL enforces them.

## Deployment sequence

1. Apply migrations.
2. Run the catalog import through the reviewed operator procedure when source data changes.
3. Deploy the API revision.
4. Deploy the web revision.

Prior healthy revisions are retained for rollback. The API keeps internal ingress throughout.
