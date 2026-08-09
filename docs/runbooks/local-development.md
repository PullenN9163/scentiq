# Local Development Runbook

This runbook covers the supported Milestones 2 and 3 developer workflows. Run commands from the repository root unless a step says otherwise.

## Before starting

Install the supported runtimes listed in the [root README](../../README.md#prerequisites), then install locked dependencies:

```powershell
pnpm install --frozen-lockfile
uv sync --directory apps/api --frozen --all-groups
```

Use `.env.example` unchanged for the standard Compose workflow. To customize local values, copy it to the Git-ignored `.env` file and use `--env-file .env` in place of `--env-file .env.example`:

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
} else {
    Write-Output "Existing .env left unchanged."
}
```

Only safe local values belong in `.env`. Never copy production credentials, Azure tokens, client secrets, storage keys, or shared connection strings into the repository.

## Host development

Host development requires PostgreSQL 18 already running at a host-reachable address. The Compose database is intentionally not published to the host, so the `db` hostname from `.env.example` works only inside the Compose network.

For a developer-owned PostgreSQL database on `localhost:5432`, set the host-specific environment and run migrations before starting the applications:

```powershell
$env:SCENTIQ_ENV = "development"
$env:DATABASE_URL = "postgresql+psycopg://scentiq_local:scentiq_local_only@localhost:5432/scentiq_local"
$env:CORS_ORIGINS = "http://localhost:3000"
$env:API_INTERNAL_URL = "http://localhost:8000"
$env:NEXT_PUBLIC_APP_ENV = "development"
pnpm api:migrate
pnpm dev
```

`pnpm dev` starts FastAPI on `http://localhost:8000` and Next.js on `http://localhost:3000`. Press `Ctrl+C` once to stop both processes. Change the example URL and local credentials when the host database uses different values.

The applications can also run in separate terminals after exporting the same environment variables:

```powershell
pnpm dev:api
```

```powershell
pnpm dev:web
```

## Clean Compose start

The standard flow builds the production images, starts PostgreSQL, applies migrations explicitly, then starts the API and frontend:

```powershell
docker compose --env-file .env.example build --pull api web
docker compose --env-file .env.example up -d db
docker compose --env-file .env.example run --rm api .venv/bin/alembic upgrade head
docker compose --env-file .env.example run --rm api .venv/bin/python -m scentiq_api.seed
docker compose --env-file .env.example up -d api web
docker compose --env-file .env.example ps
```

Wait until `db`, `api`, and `web` report `healthy`. The services bind only to the loopback interface:

| Service | Local address |
| --- | --- |
| Frontend | `http://localhost:3000` |
| Frontend API status | `http://localhost:3000/api/status` |
| API liveness | `http://localhost:8000/health/live` |
| API readiness | `http://localhost:8000/health/ready` |

The named volume `scentiq_postgres_data` preserves local database data between ordinary shutdowns.

## Migrations

Application startup does not apply migrations. Upgrade the configured host database with:

```powershell
pnpm api:migrate
uv run --directory apps/api alembic current --check-heads
```

For Compose, use the API image on the private network:

```powershell
docker compose --env-file .env.example up -d db
docker compose --env-file .env.example run --rm api .venv/bin/alembic upgrade head
docker compose --env-file .env.example run --rm api .venv/bin/alembic current --check-heads
```

CI verifies the complete cycle against an ephemeral database:

```powershell
uv run --directory apps/api alembic upgrade head
uv run --directory apps/api alembic current --check-heads
uv run --directory apps/api alembic downgrade base
uv run --directory apps/api alembic upgrade head
uv run --directory apps/api alembic current --check-heads
uv run --directory apps/api alembic check
```

`alembic downgrade base` removes every migration from the configured database. Run the full cycle only against a disposable database, never against a shared or production database.

## Smoke tests

After all Compose services are healthy, run:

```powershell
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
Invoke-RestMethod http://localhost:3000/api/status
(Invoke-WebRequest -UseBasicParsing http://localhost:3000).StatusCode
```

Expected results are:

- liveness: `status` is `ok`;
- readiness: `status` is `ready`;
- frontend API status: `api` is `available`; and
- frontend status code: `200`.

If liveness succeeds while readiness returns HTTP 503, the API process is running but cannot query PostgreSQL. Inspect the database and API logs before restarting anything.

## Logs and status

Inspect current container state and recent logs:

```powershell
docker compose --env-file .env.example ps
docker compose --env-file .env.example logs --tail 100 db api web
```

Follow API and frontend logs during reproduction, then press `Ctrl+C` to stop following without stopping the containers:

```powershell
docker compose --env-file .env.example logs --follow api web
```

Logs can contain operational details. Review them before sharing and never paste credentials or connection strings into tickets or chat.

## Shutdown

Stop and remove the ScentIQ containers and network while preserving the database volume:

```powershell
docker compose --env-file .env.example down
```

This does not remove `scentiq_postgres_data` or the locally built images.

## Safe local database reset

Resetting the Compose database permanently deletes local ScentIQ data. First stop the project and verify that the target volume is the Compose-owned ScentIQ volume:

`POSTGRES_INITDB_ARGS` is applied only when PostgreSQL initializes a fresh volume. An existing volume keeps its original authentication configuration; use this label-verified reset when it must adopt the Compose SCRAM settings.

```powershell
docker compose --env-file .env.example down
docker volume inspect scentiq_postgres_data --format '{{json .Labels}}'
```

Continue only when the labels include `com.docker.compose.project` set to `scentiq` and `com.docker.compose.volume` set to `postgres_data`. Then remove the project volume and reinitialize it:

```powershell
docker compose --env-file .env.example down --volumes
docker compose --env-file .env.example up -d db
docker compose --env-file .env.example run --rm api .venv/bin/alembic upgrade head
docker compose --env-file .env.example up -d api web
```

Do not use `docker system prune`, `docker volume prune`, wildcard removal, or Docker Desktop factory reset for this workflow; those operations can delete unrelated data.

## Docker Desktop troubleshooting on Windows

Start with read-only checks:

```powershell
docker version
docker compose version
docker info
docker compose --env-file .env.example config --quiet
docker compose --env-file .env.example ps
```

Common conditions:

- **Cannot connect to the Docker daemon or named pipe:** Open Docker Desktop, select Linux containers, and wait until the engine reports that it is running. Retry `docker version` before rerunning Compose.
- **A service remains unhealthy:** Inspect `docker compose --env-file .env.example logs --tail 100 db api web`. Readiness depends on PostgreSQL, so a database failure also makes the API unhealthy and prevents the frontend from starting.
- **Port 3000 or 8000 is already in use:** Identify the listener with `Get-NetTCPConnection -State Listen -LocalPort 3000,8000`. Stop the known owning application gracefully; do not terminate an unidentified process.
- **WSL 2 integration is unavailable:** Run `wsl --status`, confirm virtualization and WSL 2 are enabled, then restart Docker Desktop. `wsl --shutdown` interrupts every running WSL distribution, so use it only after saving work and intentionally stopping affected processes.
- **Stale ScentIQ containers:** Use `docker compose --env-file .env.example down`, then repeat the clean start. Do not remove volumes unless an intentional local database reset is required.

## Local-only secrets and Azure identity

The values `scentiq_local`, `scentiq_local_only`, and the corresponding connection URL are deliberately weak, local-only development credentials. They protect no Azure resource and must never be reused outside a developer-owned local environment.

Azure identity is a deployment-time runtime concern:

- `AZURE_CLIENT_ID` selects a user-assigned managed identity; it is an identifier, not a password.
- `AZURE_STORAGE_ACCOUNT_URL` and `AZURE_KEY_VAULT_URL` identify resources; they are not credentials.
- Azure service access uses the configured user-assigned identity without client secrets.
- Client secrets, storage keys, tokens, and production database credentials must not be stored in `.env.example`, committed `.env` files, or CI.

Leave the Azure variables and Application Insights connection string empty for ordinary local development.
