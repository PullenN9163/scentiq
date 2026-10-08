import os

import pytest

from scentiq_api.database import create_database_probe, dispose_database_probe

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="DATABASE_URL is required for PostgreSQL integration tests",
)
def test_database_probe_executes_against_postgresql() -> None:
    database_probe = create_database_probe(os.environ["DATABASE_URL"])

    try:
        database_probe()
    finally:
        dispose_database_probe(database_probe)
