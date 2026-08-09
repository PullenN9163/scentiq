import os

import pytest

_DATABASE_URL_WAS_PROVIDED_EXTERNALLY = "DATABASE_URL" in os.environ

os.environ.setdefault("SCENTIQ_ENV", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:password@localhost/scentiq_test")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if _DATABASE_URL_WAS_PROVIDED_EXTERNALLY:
        return

    skip_integration = pytest.mark.skip(
        reason="DATABASE_URL is required for PostgreSQL integration tests"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
