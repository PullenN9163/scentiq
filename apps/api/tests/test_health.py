import logging

import pytest
from fastapi.testclient import TestClient

from scentiq_api.config import Settings
from scentiq_api.main import create_app


def make_test_settings() -> Settings:
    return Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL="postgresql+psycopg://user:password@localhost/scentiq_test",
        CORS_ORIGINS="http://localhost:5173",
    )


def test_liveness_is_independent_of_database() -> None:
    def unavailable_probe() -> None:
        raise RuntimeError("database host detail")

    with TestClient(create_app(make_test_settings(), unavailable_probe)) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_ready_after_successful_probe() -> None:
    with TestClient(create_app(make_test_settings(), lambda: None)) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_sanitizes_database_failure(caplog: pytest.LogCaptureFixture) -> None:
    def unavailable_probe() -> None:
        raise RuntimeError("postgresql://user:secret@private-host/database")

    with (
        caplog.at_level(logging.ERROR, logger="scentiq_api.health"),
        TestClient(create_app(make_test_settings(), unavailable_probe)) as client,
    ):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert "secret" not in response.text
    assert "private-host" not in response.text
    assert "secret" not in caplog.text
    assert "private-host" not in caplog.text


def test_lifespan_disposes_owned_database_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    class DisposableProbe:
        def __init__(self) -> None:
            self.disposed = False

        def __call__(self) -> None:
            pass

        def dispose(self) -> None:
            self.disposed = True

    probe = DisposableProbe()
    monkeypatch.setattr("scentiq_api.main.create_database_probe", lambda _: probe)

    with TestClient(create_app(make_test_settings())):
        assert not probe.disposed

    assert probe.disposed


def test_cors_allows_only_configured_origin() -> None:
    with TestClient(create_app(make_test_settings(), lambda: None)) as client:
        allowed_response = client.get("/health/live", headers={"Origin": "http://localhost:5173"})
        untrusted_response = client.get(
            "/health/live", headers={"Origin": "https://untrusted.example"}
        )

    assert allowed_response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert allowed_response.headers["access-control-allow-credentials"] == "true"
    assert "access-control-allow-origin" not in untrusted_response.headers
