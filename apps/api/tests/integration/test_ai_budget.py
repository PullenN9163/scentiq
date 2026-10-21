"""Cross-connection PostgreSQL checks for the globally shared inference allowance."""

import os
from concurrent.futures import ThreadPoolExecutor
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import Table, create_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from scentiq_api.config import Settings
from scentiq_api.models.ai_usage import AIUsageMonth, AIUsageReservation
from scentiq_api.services.ai_ranking import reserve_budget

pytestmark = pytest.mark.integration


def test_concurrent_inference_reservations_never_exceed_monthly_cap() -> None:
    engine = create_engine(os.environ["DATABASE_URL"])
    schema = "inference_budget_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    try:
        cast(Table, AIUsageMonth.__table__).create(isolated)
        cast(Table, AIUsageReservation.__table__).create(isolated)
        settings = Settings(AI_MONTHLY_BUDGET_USD=0.02)
        with ThreadPoolExecutor(max_workers=8) as executor:
            reservations = list(
                executor.map(lambda _: reserve_budget(isolated, settings, 5000), range(20))
            )
        assert sum(reservation is not None for reservation in reservations) == 4
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()
