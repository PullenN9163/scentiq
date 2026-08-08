# Milestone 1: Repository and Application Foundation

## Status

Approved for implementation on August 8, 2026.

## Objective

Establish a secure, reproducible application foundation for ScentIQ before domain features are introduced. The milestone delivers a working Next.js frontend, a FastAPI backend, a PostgreSQL migration path, local containers, automated quality gates, and explicit runtime contracts without deploying application resources to Azure.

## Scope

Milestone 1 includes:

- a lightweight monorepo with `apps/web` and `apps/api`;
- a root developer workflow for installing, running, testing, and validating both applications;
- local PostgreSQL 18, backend, and frontend services through Docker Compose;
- configuration validation and a secret-safe `.env.example`;
- backend liveness and database-aware readiness endpoints;
- an Alembic migration environment that can initialize an empty database;
- a minimal frontend shell that reports backend availability;
- production-oriented, non-root container images;
- continuous integration for tests, linting, type checking, builds, migration checks, and Compose validation; and
- professional setup and operational documentation.

The milestone does not include fragrance-domain tables, collection management, authentication, file uploads, Azure application deployment, external integrations, recommendations, or analytics.

## Repository architecture

The repository uses a lightweight monorepo:

```text
.
|-- apps/
|   |-- api/
|   `-- web/
|-- docs/
|   |-- architecture/
|   `-- runbooks/
|-- .github/workflows/
|-- compose.yaml
|-- package.json
|-- pnpm-lock.yaml
`-- README.md
```

The root `package.json` provides cross-platform orchestration commands. JavaScript dependencies are managed with pnpm and locked at the repository root. Python dependencies are declared in `apps/api/pyproject.toml` and locked with uv in `apps/api/uv.lock`. Each application remains independently buildable and testable.

The supported local runtimes are Node.js 24, pnpm 11, Python 3.12, uv 0.12, Docker Engine 29, and Docker Compose 5. Next.js requires Node.js 20.9 or newer, so Node.js 24 is the project baseline. PostgreSQL 18 matches the Azure development database.

## Frontend

The frontend uses Next.js 16 with the App Router, React 19, and strict TypeScript. It provides a small ScentIQ foundation page rather than a product dashboard. The page displays the application identity and an API status indicator backed by a narrow internal route handler.

The route handler requests the backend liveness endpoint using the server-only `API_INTERNAL_URL` setting. It returns a stable frontend-owned response and converts backend timeouts or connection failures into an `unavailable` state. Browser code never receives database credentials, Azure credentials, Key Vault references, or internal container hostnames.

`NEXT_PUBLIC_APP_ENV` is the only initial browser-visible setting. Values needed only by the Next.js server remain unprefixed.

Frontend quality gates are:

- unit and component tests with Vitest and Testing Library;
- ESLint;
- TypeScript checking without emission; and
- a production Next.js build.

## Backend

The backend uses Python 3.12, FastAPI, Pydantic Settings, SQLAlchemy 2, Alembic, and psycopg 3. Application creation follows a factory pattern so configuration and database dependencies can be tested without global mutable state.

The initial HTTP contract is:

- `GET /health/live` returns HTTP 200 with `{"status":"ok"}` whenever the process can serve requests.
- `GET /health/ready` runs `SELECT 1` through the configured database engine. It returns HTTP 200 with `{"status":"ready"}` on success and HTTP 503 with `{"status":"not_ready"}` when the database is unavailable.

The readiness response does not expose exception text, hostnames, connection strings, or credentials. Detailed failures are logged to standard output for the runtime log collector.

The API remains stateless. It writes no durable data to the container filesystem and keeps no request state in process memory beyond bounded framework and connection-pool state.

Backend quality gates are:

- pytest tests against application behavior;
- Ruff lint and format checks;
- mypy strict type checking; and
- Alembic checks against a clean PostgreSQL database.

## Configuration and secrets

Configuration comes from environment variables and is validated at process startup. The initial contract is:

- `SCENTIQ_ENV`: `development`, `test`, or `production`;
- `DATABASE_URL`: a SQLAlchemy psycopg URL;
- `CORS_ORIGINS`: a comma-separated allowlist with no wildcard in production;
- `AZURE_CLIENT_ID`: optional locally and required when the user-assigned Azure identity is selected for deployment;
- `AZURE_STORAGE_ACCOUNT_URL`: optional until storage features are implemented;
- `AZURE_KEY_VAULT_URL`: optional until secrets are read from Key Vault;
- `API_INTERNAL_URL`: the server-only backend URL used by Next.js; and
- `NEXT_PUBLIC_APP_ENV`: the non-sensitive environment label rendered by the frontend.

`.env.example` contains variable names and safe local placeholders only. Real `.env` files, credentials, tokens, passwords, certificate material, and credential-bearing connection strings are ignored by Git. Local Compose credentials are explicitly development-only and must not be reused outside the local Docker network.

Azure application code will use `DefaultAzureCredential` when Azure service integration begins. Shared storage keys and application secrets are not part of this milestone.

## Database and migrations

Docker Compose provides PostgreSQL 18 with a health check and a named local volume. The API waits for PostgreSQL health before running.

Alembic reads the database URL through the same validated application settings as the API. A baseline revision establishes the migration chain without introducing domain tables. Verification creates an empty test database, upgrades it to `head`, confirms that the database is at the current head, downgrades to `base`, and upgrades to `head` again. Milestone 2 will add the first domain schema revision.

Application startup does not run migrations automatically. Local and deployment workflows run migrations as an explicit, observable step before starting a new application revision.

## Local container workflow

`compose.yaml` defines `db`, `api`, and `web` services:

- `db` uses PostgreSQL 18, persists data in a named volume, and exposes a health check.
- `api` builds the backend image, depends on a healthy database, exposes port 8000, and uses the liveness endpoint for its container health check.
- `web` builds the frontend image, depends on a healthy API, exposes port 3000, and reaches the API over the Compose network.

The Compose file contains safe local defaults and supports overrides from an ignored `.env` file. `docker compose config` must succeed without access to private credentials. The documented clean-start workflow must build the images, initialize the database, run migrations, start the services, and pass HTTP smoke checks.

## Container and deployment contract

Both applications use multi-stage Dockerfiles with pinned major runtime images and locked dependency installation. Final stages run as non-root users, expose only their application ports, and receive configuration at runtime rather than build time.

The backend image starts one application process and emits logs to standard output and standard error. The frontend image uses Next.js standalone output. Neither image embeds `.env` files, source-control metadata, local caches, test artifacts, or credentials.

Milestone 1 produces deployable image contracts but does not create an Azure Container Registry, Container App, Static Web App, OAuth application, or deployment secret. Azure deployment automation will consume these image and configuration contracts in a later milestone.

## Continuous integration

GitHub Actions runs on pull requests to `main` and pushes to `dev`. It uses least-privilege read-only repository permissions and no Azure credentials.

The workflow runs independent frontend and backend checks plus an integration job with PostgreSQL 18. Required evidence includes:

- dependency installation from committed lockfiles;
- frontend tests, lint, type checking, and production build;
- backend tests, Ruff, mypy, and migration verification;
- Docker Compose configuration validation; and
- production image builds.

Caching may accelerate package installation but must not bypass lockfile enforcement or required checks.

## Error handling and observability

Configuration errors fail startup with a clear variable-level message that never includes secret values. Health endpoints use stable response bodies and status codes. Database readiness failures are logged with structured context while the HTTP response remains sanitized. Frontend backend-status failures render an unavailable state without failing the page.

Request logs include method, path, status, and duration. They exclude authorization headers, cookies, request bodies, database URLs, and environment values. A full telemetry and alerting design is deferred until Azure deployment.

## Acceptance criteria

Milestone 1 is complete only when all of the following are true:

1. A fresh checkout can install dependencies from committed lockfiles using documented commands.
2. Frontend and backend test, lint, type-check, and build commands pass.
3. Backend liveness and readiness behavior is covered by tests, including an unavailable database.
4. The frontend API-status behavior is covered for available and unavailable backends.
5. Configuration rejects missing required values and unsafe production CORS without leaking values.
6. Alembic can upgrade an empty PostgreSQL 18 database to `head`, verify current heads, downgrade to `base`, and upgrade again.
7. `docker compose config` succeeds using only safe example configuration.
8. A clean Compose build and startup makes the frontend, backend liveness endpoint, and backend readiness endpoint reachable.
9. Both final container images run as non-root users and contain no `.env` file or Git metadata.
10. GitHub Actions encodes the same required quality checks without Azure secrets.
11. Repository documentation explains setup, configuration, migrations, tests, containers, and milestone boundaries.
12. The privacy hook accepts all official files, no private working artifacts are staged, and the staged diff is reviewed before each commit.
