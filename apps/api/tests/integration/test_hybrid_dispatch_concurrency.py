"""Overlapping bridge executions must not dispatch the same pending job."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import Table, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from scentiq_api.hybrid.contracts import RecommendationJobInput
from scentiq_api.hybrid.runtime import HybridDispatcher
from scentiq_api.hybrid.transport import InMemoryHybridTransport
from scentiq_api.models import AsyncJob, User

pytestmark = pytest.mark.integration


class BlockingTransport(InMemoryHybridTransport):
    def __init__(self, started: Event, release: Event) -> None:
        super().__init__()
        self.started = started
        self.release = release
        self.enqueued: list[tuple[str, dict[str, Any]]] = []

    def upload_json(self, name: str, value: dict[str, Any]) -> None:
        self.started.set()
        if not self.release.wait(timeout=10):
            raise TimeoutError("test dispatch was not released")
        super().upload_json(name, value)

    def enqueue(self, queue: str, value: dict[str, Any]) -> None:
        self.enqueued.append((queue, value))
        super().enqueue(queue, value)


class RecordingTransport(InMemoryHybridTransport):
    def upload_json(self, _name: str, _value: dict[str, Any]) -> None:
        raise AssertionError("a locked job must be skipped before upload")

    def enqueue(self, _queue: str, _value: dict[str, Any]) -> None:
        raise AssertionError("a locked job must be skipped before enqueue")


def test_concurrent_bridge_dispatchers_skip_a_job_locked_by_another_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], pool_size=5)
    schema = f"hybrid_dispatch_{uuid4().hex}"
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    try:
        cast(Table, User.__table__).create(isolated)
        cast(Table, AsyncJob.__table__).create(isolated)
        factory = sessionmaker(bind=isolated, expire_on_commit=False)
        with factory.begin() as session:
            session.add(
                AsyncJob(
                    job_type="recommendation_bundle",
                    status="pending",
                    user_id=None,
                    input_version=1,
                    idempotency_key=f"recommendation_bundle:{uuid4()}:1",
                    reason="concurrency_test",
                )
            )
        monkeypatch.setattr(
            HybridDispatcher,
            "_recommendation_input",
            lambda _self, job: RecommendationJobInput(
                job_id=job.id,
                input_version=job.input_version or 0,
                catalog_version="catalog-test",
                collection=[],
            ),
        )
        started = Event()
        release = Event()
        transport = BlockingTransport(started, release)

        def first_dispatch() -> int:
            with factory.begin() as session:
                return HybridDispatcher(
                    session, transport, catalog_version="catalog-test"
                ).dispatch_pending(limit=1)

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(first_dispatch)
            assert started.wait(timeout=10)
            with factory.begin() as session:
                concurrent_count = HybridDispatcher(
                    session, RecordingTransport(), catalog_version="catalog-test"
                ).dispatch_pending(limit=1)
            release.set()
            assert first.result(timeout=10) == 1

        assert concurrent_count == 0
        assert len(transport.enqueued) == 1
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()
