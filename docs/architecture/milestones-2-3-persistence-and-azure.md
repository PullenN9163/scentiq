# Milestones 2 and 3: Persistence and Azure Deployment

## Status

Approved for implementation on August 9, 2026.

## Objective

Milestone 2 introduces the persistent fragrance domain, deterministic demo data,
and a typed read-only API. Milestone 3 makes that foundation continuously
deployable to the existing Azure development environment. Both milestones extend
the verified Milestone 1 foundation without changing its frontend presentation or
health-status behavior.

## Scope

Milestone 2 includes:

- SQLAlchemy models and an Alembic revision for the initial fragrance domain;
- request-scoped database sessions, repositories, and application services;
- an idempotent seed command for a demo user, catalog, and collection;
- typed fragrance-list, fragrance-detail, and collection endpoints; and
- PostgreSQL-backed migration, seed, repository, and API tests.

Milestone 3 includes:

- Python 3.14 for the API runtime and Node.js 24 for the web runtime;
- the existing production-oriented Docker and local Compose workflows;
- modular Bicep for the complete development topology;
- an Azure Container Registry, Application Insights, and web and API Container
  Apps added to the existing Azure foundation;
- managed-identity access to ACR, Blob Storage, and Key Vault;
- OpenTelemetry-based request, error, and trace collection;
- GitHub Actions validation and an OIDC-authenticated deployment workflow; and
- an explicit, observable database migration step before application rollout.

The milestones do not add authentication, collection mutations, file uploads,
weather integrations, recommendations, weekly planning, or new frontend product
features. Those remain later milestones.

## Existing foundation

The implementation reuses these verified contracts:

- the Next.js App Router application and its ScentIQ foundation page;
- the same-origin `/api/status` browser boundary;
- FastAPI application creation, liveness, readiness, CORS, and secret-safe
  request logging;
- PostgreSQL 18 in local Compose;
- explicit Alembic migrations;
- non-root, multi-stage API and web images;
- locked pnpm and uv dependencies; and
- frontend, backend, migration, Compose, and image checks in continuous
  integration.

The existing UI is a compatibility boundary. Its rendered copy, layout,
responsive behavior, API-status indicator, and accessibility behavior remain
unchanged. Existing frontend tests continue to guard that boundary.

## Application architecture

The browser continues to communicate only with Next.js. Milestone 2 exposes API
routes for future server-side frontend use, but does not connect them to the UI.
The API uses request-scoped SQLAlchemy sessions and separates transport,
application, and persistence concerns:

```text
FastAPI router
    -> application service
        -> repository
            -> SQLAlchemy session
                -> PostgreSQL 18
```

The API package is organized by responsibility:

```text
src/scentiq_api/
|-- api/v1/              versioned HTTP routers
|-- models/              SQLAlchemy mappings and metadata
|-- repositories/        persistence queries
|-- schemas/             Pydantic request and response contracts
|-- services/            application orchestration
|-- database.py          engine and session lifecycle
|-- health.py            existing health contracts
|-- logging.py           existing request logging
|-- seed.py              deterministic seed command
`-- main.py              application composition
```

Repositories receive a SQLAlchemy `Session` and contain database queries only.
Services receive repositories and define use-case behavior. Routers translate
service results into Pydantic responses and HTTP status codes. This boundary
allows tests to exercise real PostgreSQL behavior while keeping endpoint wiring
small and explicit.

## Database conventions

Application entities use PostgreSQL UUID primary keys. Seeded entities use fixed
UUID values; runtime-created entities use UUID version 4. Timestamps use
timezone-aware PostgreSQL columns and UTC values. Mutable top-level entities have
`created_at` and `updated_at` columns.

Domain values such as note stage, ownership type, status, projection, season,
and occasion use bounded text columns with database check constraints. This
keeps migrations understandable and avoids PostgreSQL enum-replacement overhead.
Monetary amounts use fixed-precision numeric columns. Scores and weights include
database range checks.

Foreign keys use restrictive deletion by default. Association and dependent
records may cascade only when their owning parent cannot have an independent
lifecycle. User-owned rows always retain an explicit `user_id` boundary in
preparation for Milestone 4.

## Initial schema

The initial domain revision creates exactly these required tables.

### Users and preferences

`users` stores `id`, unique normalized `email`, `display_name`, `is_demo`,
`created_at`, and `updated_at`.

`user_preferences` is a one-to-one extension keyed by `user_id`. It stores
nullable preferred season, occasion, projection, longevity, and maximum spray
count values plus timestamps. Preferences are deliberately small until later
recommendation work proves additional fields are useful.

### Catalog

`brands` stores `id`, unique `name`, unique `slug`, and timestamps.

`fragrances` stores `id`, `brand_id`, `name`, `concentration`, optional
`release_year`, optional `description`, optional `image_blob_path`, optional
zero-to-ten `longevity_score`, optional `projection_level`, and timestamps. A
brand, fragrance name, and concentration combination is unique.

`notes` and `accords` each store `id`, a unique `name`, and a unique `slug`.

`fragrance_notes` associates a fragrance and note with a `stage` of `top`,
`middle`, or `base`. The fragrance, note, and stage form its primary key.

`fragrance_accords` associates a fragrance and accord with a zero-to-one
`weight`. The fragrance and accord form its primary key.

`fragrance_seasons` associates a fragrance with `spring`, `summer`, `fall`, or
`winter` and a zero-to-one weight. `fragrance_occasions` uses the same structure
for `work`, `casual`, `date`, `dinner`, `party`, `formal`, `gym`, `travel`, and
`other`.

### Collection and feedback

`user_collection` stores `id`, `user_id`, `fragrance_id`, `ownership_type`,
optional bottle and remaining milliliters, optional purchase price and date,
optional one-to-five user rating, optional custom longevity and projection,
`status`, and timestamps. Ownership is `bottle`, `decant`, or `sample`; status is
`owned`, `wishlist`, `finished`, or `sold`. The dedicated wishlist table adds
shopping priority and rationale for items whose collection status is `wishlist`.

`wear_logs` stores `id`, `user_id`, `collection_item_id`, `worn_at`, optional
spray count, optional occasion and setting, optional notes, and `created_at`.

`wear_feedback` is keyed by `id` and has a unique `wear_log_id`. It stores the
owning `user_id`, optional one-to-five rating, optional longevity and projection
assessments, optional comments, and `created_at`.

`wishlists` stores `id`, `user_id`, `fragrance_id`, a one-to-five priority,
optional reason, and timestamps. A user may wishlist a fragrance only once.

### Planning context

`calendar_events` stores `id`, `user_id`, optional external reference, a safely
reduced title, start and end timestamps, normalized event type, optional setting
and formality, `is_hidden`, and timestamps. External references are unique per
user when present.

`weather_snapshots` stores `id`, `user_id`, location label, observation or
forecast timestamp, temperature in Celsius, optional humidity and precipitation
probability, normalized condition, source, and `created_at`.

### Recommendations and layering

`recommendations` stores `id`, `user_id`, recommendation date and context,
selected `fragrance_id`, zero-to-one-hundred score, recommended sprays,
structured reasons and warnings, algorithm version, and timestamps.

`recommendation_candidates` stores `id`, `recommendation_id`, `fragrance_id`,
rank, zero-to-one-hundred score, and structured score components. A fragrance
appears once per recommendation and ranks are unique within a recommendation.

`layering_logs` stores `id`, `user_id`, two distinct fragrance identifiers,
`worn_at`, optional one-to-five rating, optional notes, and `created_at`.

Indexes cover catalog sorting, user collection lookup, chronological wear and
event lookup, forecast time, and recommendation history. No speculative tables
or indexes are included.

## Migration and session lifecycle

The existing Alembic baseline remains the start of the revision chain. The
domain revision imports the shared SQLAlchemy metadata and creates all required
tables, constraints, and indexes. Its downgrade removes them in reverse
dependency order.

Application startup does not run migrations. Local development, continuous
integration, and Azure deployment invoke Alembic explicitly. A clean PostgreSQL
database must reach the current schema solely through `alembic upgrade head`,
and the full downgrade and second-upgrade cycle must remain valid.

The database module owns an engine and a session factory. FastAPI exposes one
session per request through a dependency that commits no implicit work, rolls
back failed transactions, and always closes the session. The existing readiness
probe continues using its narrow `SELECT 1` contract.

## Deterministic seed data

The seed command uses a single transaction and fixed identifiers. It performs
conflict-safe upserts on natural keys and reconciles association rows. Running
it repeatedly produces the same logical dataset without duplicate users,
catalog records, associations, or collection items.

The seed contains:

- one clearly identified demo user and one preference record;
- a fictional, clearly labeled demo catalog of approximately 15 fragrances;
- reusable note and accord vocabularies;
- season and occasion suitability metadata; and
- a representative demo collection containing bottles, decants, and samples.

Fictional catalog data avoids presenting unverified commercial metadata as
fact. Future catalog ingestion can replace it without changing the seed or API
contracts.

The command exits successfully on the first and second run and reports stable
entity counts without emitting credentials or connection details.

## HTTP API

The existing endpoints remain unchanged:

- `GET /health/live` returns `200 {"status":"ok"}`;
- `GET /health/ready` returns the existing database-aware readiness contract;
  and
- the Next.js `GET /api/status` route retains its current response contract.

Milestone 2 adds:

- `GET /health` as a compatibility alias for process liveness;
- `GET /api/v1/fragrances` returning all seeded fragrances ordered by brand and
  name;
- `GET /api/v1/fragrances/{id}` returning one fragrance with brand, notes,
  accords, seasons, and occasions; and
- `GET /api/v1/collection` returning the demo user's collection with nested
  fragrance summaries.

Until authentication arrives in Milestone 4, the collection endpoint resolves
the fixed demo user in application configuration. Browser-supplied user IDs are
not accepted.

All success responses use typed Pydantic models. Unknown or malformed fragrance
identifiers return a stable `404 {"detail":"Fragrance not found"}` response.
Database exceptions are logged through sanitized fixed-field records and return
a generic server error; exception messages, statements, parameters, connection
strings, and credentials never cross the HTTP or logging boundary.

## Azure topology

The development deployment uses the existing resource group
`scentiq-rg-dev-eus`. The current foundation contains:

- Log Analytics workspace `scentiq-law-dev-us` in East US;
- Storage account `scentiqstrgdevus` in East US;
- Key Vault `scentiq-kv-dev-eus` in East US;
- PostgreSQL Flexible Server `scentiq-pg-dev-eus` in North Central US;
- user-assigned managed identity `scentiq-api-id-dev-eus` in East US; and
- Container Apps environment `scentiq-cae-dev-eus` in East US.

The region difference for PostgreSQL is the approved subscription-capacity
exception. The deployment adds an ACR Basic registry, Application Insights, an
externally reachable web Container App, an internally reachable API Container
App, and a manual migration Container Apps Job.

```text
Internet
    -> web Container App (external HTTPS ingress)
        -> api Container App (internal HTTPS ingress)
            -> PostgreSQL Flexible Server
            -> private Blob Storage
            -> Key Vault

ACR -> managed-identity image pulls
web/api/migration -> Log Analytics + Application Insights
```

Only the web application has external application ingress. The API is reachable
from the web application through the Container Apps environment. HTTPS is
required. PostgreSQL retains only the minimum connectivity needed by the current
prototype; Bicep parameters expose network choices so a later reviewed private
network migration does not require application changes. No unrestricted
`0.0.0.0/0` firewall rule is created.

## Bicep structure

Infrastructure code lives under `infra/`:

```text
infra/
|-- main.bicep
|-- modules/
|   |-- monitoring.bicep
|   |-- identity.bicep
|   |-- registry.bicep
|   |-- storage.bicep
|   |-- key-vault.bicep
|   |-- postgres.bicep
|   |-- container-environment.bicep
|   |-- container-app.bicep
|   `-- migration-job.bicep
`-- parameters/
    `-- dev.bicepparam
```

The root template supports a fresh environment and an adoption mode for the
pre-existing development foundation. Adoption mode references existing resource
identifiers and creates only missing resources. Every module remains usable by
a future production parameter file.

Parameters cover naming prefix, environment name, regions, existing-resource
mode and names, PostgreSQL SKU, container CPU and memory, min and max replicas,
image tags, and allowed network inputs. Secrets are secure parameters or runtime
Key Vault references and never have source-controlled defaults.

## Identity and secrets

The API user-assigned identity receives `AcrPull`, `Storage Blob Data
Contributor`, and `Key Vault Secrets User` at the narrow resource scopes. The web
application receives only the identity permissions it requires. Role assignment
names are deterministic so deployments remain idempotent.

Container Apps pull images with managed identity where supported. Runtime
configuration is split between ordinary environment values and secret-backed
values. Database credentials are supplied through a Key Vault-backed Container
App secret. GitHub stores only non-secret Azure identifiers and uses workload
identity federation; no long-lived service-principal password is introduced.

Blob containers remain private. Milestone 3 prepares identity access but does
not add upload or download product behavior.

## Images and runtime configuration

The existing multi-stage Dockerfiles remain the starting point. The API image
moves to an official Python 3.14 slim base, installs the locked production
environment, runs one FastAPI/Uvicorn process, and remains non-root. The web image
continues using Node.js 24, locked pnpm installation, Next.js standalone output,
and a non-root final stage.

Local Compose retains PostgreSQL 18, explicit migrations, the API, and the web
application. Product images receive Milestone 3 tags rather than the current
Milestone 1 tags. Local ports remain loopback-bound.

The API adds optional OpenTelemetry configuration. When an Application Insights
connection string is present, it exports server requests, errors, and traces.
When absent, local development remains functional without network exporters. The
web server captures request and backend-proxy failures through the supported
Azure Monitor/OpenTelemetry integration without exposing browser secrets.

## Deployment workflow

Pull requests to `main` and pushes to `dev` retain all current quality gates.
Container validation explicitly builds both production images. Bicep compilation
and validation become additional gates.

A protected deployment workflow runs on `main` and by explicit manual dispatch:

1. authenticate to Azure through GitHub OIDC;
2. validate the target resource-group deployment;
3. deploy or update infrastructure;
4. build immutable images tagged with the commit SHA;
5. push both images to ACR;
6. update and start the manual migration job;
7. require successful migration completion;
8. deploy new API and web revisions; and
9. smoke-test public web and health behavior.

Migrations never run during ordinary application replica startup. A migration
failure stops deployment before traffic moves to the new application revision.
The previously healthy revision remains available for rollback.

## Error handling and observability

Application failures use stable, sanitized HTTP responses. Structured logs keep
the existing request fields and add trace correlation where available. Database,
Key Vault, Blob, deployment, and migration errors exclude secrets and private
payloads.

Application Insights collects request duration, response status, unhandled
exceptions, and distributed traces across web-to-API calls. Health endpoints are
available to Container Apps probes, but routine probe traffic may be sampled or
filtered to control noise. Logs and telemetry never include authorization
headers, cookies, database URLs, seed data details, or future private user notes.

## Testing and verification

Milestone 2 uses test-first development. PostgreSQL-backed tests prove:

- the domain revision upgrades an empty database and downgrades cleanly;
- required constraints and relationships are enforced;
- the seed command succeeds twice with stable counts;
- the fragrance list is typed, ordered, and populated;
- fragrance detail returns nested catalog relationships;
- an unknown fragrance returns the stable not-found contract;
- the demo collection returns only the configured demo user's rows; and
- existing health and secret-redaction behavior remains intact.

Milestone 3 verification proves:

- frontend tests, lint, type checking, and production build pass without UI
  changes;
- backend tests, Ruff, mypy, package build, and Python 3.14 execution pass;
- Alembic upgrade, head check, downgrade, second upgrade, drift check, and seed
  idempotence pass against PostgreSQL 18;
- both production images build, run as non-root, and pass health checks;
- local Compose starts the complete stack and passes browser/API smoke tests;
- Bicep compiles and validates against the development resource group;
- GitHub Actions workflow files parse and encode the required gates;
- Azure deployment creates or updates only the intended resources;
- the web app is publicly reachable while the API has no public ingress;
- migration execution, API readiness, web health, logs, traces, and revision
  state are verified; and
- repository status, staged paths, staged diff, privacy checks, and tracked-file
  scans contain only intentional product and engineering artifacts.

## Acceptance criteria

Milestones 2 and 3 are complete only when all of the following are true:

1. All 19 required domain tables are created by Alembic from an empty
   PostgreSQL 18 database.
2. The migration chain upgrades, downgrades, re-upgrades, and reports no model
   drift.
3. The deterministic seed command can run twice with stable counts and no
   duplicate corruption.
4. `/health`, the existing health routes, fragrance list, fragrance detail, and
   demo collection endpoints pass typed API tests.
5. Unknown fragrance identifiers and infrastructure failures preserve the
   documented sanitized error boundary.
6. The frontend UI and API-status behavior remain visually and functionally
   unchanged, with all existing frontend tests passing.
7. The API runs and passes its full quality suite on Python 3.14; the web build
   remains on Node.js 24.
8. Local Compose can rebuild the database from migrations, seed it, and start
   healthy database, API, and web services.
9. Both production images build and run as non-root users.
10. Modular Bicep represents the full target topology, validates, and safely
    adopts the existing development foundation.
11. Managed identities and least-privilege role assignments provide image pull,
    Blob, and Key Vault access without source-controlled secrets.
12. CI validates frontend, backend, migrations, images, Compose, and Bicep.
13. The OIDC deployment workflow uses immutable image tags and an explicit
    migration gate.
14. The Azure web application has public HTTPS ingress, the API has internal
    ingress, and both pass their intended health checks.
15. Application Insights receives sanitized request, error, and trace telemetry.
16. README and operational documentation explain local persistence, seeding,
    migrations, Azure architecture, deployment, configuration, and recovery.
17. Completed work is reviewed, committed, and pushed to `dev` without private
    planning artifacts or AI-tool metadata.
