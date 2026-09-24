# ScentIQ

ScentIQ is a fragrance intelligence application with a Next.js frontend, a FastAPI API, a PostgreSQL fragrance catalog and collection model, and an Azure Container Apps deployment foundation. Milestones 2 and 3 add persistent demo-domain data and continuously deployable infrastructure while preserving the original frontend presentation.

Members sign in with Clerk and own persistent profiles, preferences, collections, wear history and private custom fragrances. Weekly planning, layering, discovery, the agent, and the weather, event and recommendation cards on Today remain clearly labelled previews.

Uploads, external fragrance datasets, live weather and calendar connections, notifications, recommendation scoring and language-model agent calls remain future work. See the [authenticated application architecture](docs/architecture/authenticated-personal-application.md) for the current boundaries and runtime contracts, and the [Milestones 2 and 3 architecture](docs/architecture/milestones-2-3-persistence-and-azure.md) for the persistence and Azure foundation beneath them.

## Architecture

The repository is a lightweight monorepo:

- `apps/web`: Next.js 16, React 19, and strict TypeScript;
- `apps/api`: Python 3.14, FastAPI, SQLAlchemy, Alembic, and psycopg;
- `infra`: modular Bicep for the Azure development topology;
- `compose.yaml`: PostgreSQL 18, API, and web services for local containers; and
- `.github/workflows/ci.yml`: independent frontend, backend, and container quality gates.

The browser calls the frontend's same-origin `/api/status` route. The Next.js server calls the backend liveness endpoint over `API_INTERNAL_URL`; the backend readiness endpoint checks PostgreSQL. Database migrations are always an explicit step and never run automatically when the API starts.

## Prerequisites

The supported development baseline is:

- Node.js 24;
- pnpm 11.16.0;
- Python 3.14;
- uv 0.12;
- Docker Engine 29 with Docker Compose 5 for container workflows; and
- PostgreSQL 18 when running the API directly on the host.

Git and a PowerShell-compatible terminal are also recommended. Confirm the installed tools with:

```powershell
node --version
pnpm --version
uv --version
uv run --directory apps/api python --version
docker version
docker compose version
```

## Install dependencies

From the repository root, install both locked dependency sets:

```powershell
pnpm install:all
```

The equivalent explicit commands are:

```powershell
pnpm install --frozen-lockfile
uv sync --directory apps/api --frozen --all-groups
```

## Run locally

For the most reproducible start, use Docker Compose:

```powershell
docker compose --env-file .env.example build --pull api web
docker compose --env-file .env.example up -d db
docker compose --env-file .env.example run --rm api .venv/bin/alembic upgrade head
docker compose --env-file .env.example run --rm api .venv/bin/python -m scentiq_api.seed
docker compose --env-file .env.example up -d api web
docker compose --env-file .env.example ps
```

Open the frontend at [http://localhost:3000](http://localhost:3000). The API endpoints are:

- [http://localhost:8000/health/live](http://localhost:8000/health/live) — process liveness;
- [http://localhost:8000/health/ready](http://localhost:8000/health/ready) — database-aware readiness; and
- [http://localhost:3000/api/status](http://localhost:3000/api/status) — frontend-owned API availability.

To run both applications on the host, provide a PostgreSQL 18 database reachable from the host, export the required environment variables, apply migrations, and start the root development command:

```powershell
$env:SCENTIQ_ENV = "development"
$env:DATABASE_URL = "postgresql+psycopg://scentiq_local:scentiq_local_only@localhost:5432/scentiq_local"
$env:CORS_ORIGINS = "http://localhost:3000"
$env:API_INTERNAL_URL = "http://localhost:8000"
$env:NEXT_PUBLIC_APP_ENV = "development"
pnpm api:migrate
pnpm dev
```

The example password is for a developer-owned local database only. Do not reuse it in shared, test, staging, production, or Azure environments. The Compose URL in `.env.example` uses the hostname `db`; host processes must use a hostname reachable from the host, such as `localhost`.

## Root commands

| Command | Purpose |
| --- | --- |
| `pnpm install:all` | Install JavaScript and Python dependencies from committed lockfiles. |
| `pnpm dev` | Run the API and frontend development servers together. |
| `pnpm test` | Run backend unit tests and frontend tests. |
| `pnpm lint` | Run Ruff and ESLint checks. |
| `pnpm typecheck` | Run mypy and TypeScript checks. |
| `pnpm build` | Build the production frontend. |
| `pnpm api:migrate` | Upgrade the configured database to the current Alembic head. |
| `pnpm api:seed` | Idempotently seed the fictional demo catalog and collection. |
| `pnpm api:reconcile-deletions` | Purge accounts whose deletion webhook never completed. Accepts `--dry-run`. |
| `pnpm contracts` | Regenerate `apps/api/openapi.json` and the frontend types from it. |
| `pnpm contracts:check` | Fail if the committed API contract has drifted from the application. |
| `pnpm compose:config` | Validate Compose using safe example configuration. |
| `pnpm verify` | Run unit tests, linting, type checking, the frontend build, and Compose validation. |

PostgreSQL integration tests require a reachable database and an exported `DATABASE_URL`:

```powershell
uv run --directory apps/api pytest -m integration
```

## Authentication

ScentIQ is an invite-only authenticated application. Clerk is the identity provider; the browser talks only to Next.js, which calls the internally hosted FastAPI service.

Running the app signed in requires a Clerk application and the variables listed in `.env.example`. Two are easy to miss:

- **The Clerk JWT template must include an `email` claim.** A member record is created on their first authenticated request, and the verified token is the only trustworthy source for their email address. Without the claim, every request fails with `401`.
- **`INTERNAL_SERVICE_TOKEN` must be identical** for the web and API processes. It guards the internal identity-event endpoint that the account-deletion webhook forwards to.

Without `CLERK_ISSUER` the API fails closed: protected endpoints return `503 authentication_unavailable` rather than serving unauthenticated traffic.

See the [identity and accounts runbook](docs/runbooks/identity-and-accounts.md) for setup, deployment order and troubleshooting, and the [authenticated application architecture](docs/architecture/authenticated-personal-application.md) for the design.

## Configuration and credentials

Runtime configuration comes from environment variables and is validated when the API starts. `.env.example` contains safe, deliberately weak local defaults; real `.env` files are ignored by Git. Browser-visible configuration is limited to `NEXT_PUBLIC_APP_ENV`. Database URLs, `API_INTERNAL_URL`, and Azure settings remain server-side.

The local PostgreSQL username and password are not Azure credentials. `AZURE_CLIENT_ID` identifies a user-assigned managed identity and is not a client secret. `AZURE_STORAGE_ACCOUNT_URL` and `AZURE_KEY_VAULT_URL` are resource endpoints. `APPLICATIONINSIGHTS_CONNECTION_STRING` is optional locally and enables server-side OpenTelemetry export when configured. Never add tokens, client secrets, storage keys, database URLs, or production telemetry connection strings to `.env.example`, source control, or CI.

## Development guide

The [local-development runbook](docs/runbooks/local-development.md) covers host development, a clean Compose start, migrations, smoke tests, logs, shutdown, safe database reset, and Docker Desktop troubleshooting.

The [Azure deployment runbook](docs/runbooks/azure-deployment.md) covers Bicep adoption, OIDC configuration, immutable images, migration gating, smoke tests, and rollback.
