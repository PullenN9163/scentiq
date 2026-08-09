FROM ghcr.io/astral-sh/uv:0.12.2 AS uv

FROM python:3.12-slim-bookworm AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --gid 10001 scentiq \
    && useradd --uid 10001 --gid scentiq --no-create-home --shell /usr/sbin/nologin scentiq

COPY --from=builder --chown=scentiq:scentiq /app/.venv ./.venv
COPY --from=builder --chown=scentiq:scentiq /app/src ./src
COPY --from=builder --chown=scentiq:scentiq /app/migrations ./migrations
COPY --from=builder --chown=scentiq:scentiq /app/alembic.ini ./alembic.ini

USER scentiq

EXPOSE 8000

CMD [".venv/bin/fastapi", "run", "src/scentiq_api/main.py", "--host", "0.0.0.0", "--port", "8000"]
