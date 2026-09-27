import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from scentiq_api.models import Base

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


@pytest.fixture
def engine() -> Iterator[Engine]:
    """In-memory SQLite with foreign keys enforced.

    Foreign keys are off by default in SQLite; without the pragma the cascade
    tests would pass without actually cascading.
    """
    created = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(created, "connect")
    def enforce_foreign_keys(connection: DBAPIConnection, _: object) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(created)
    try:
        yield created
    finally:
        created.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as active:
        yield active
