import logging
from typing import cast

import pytest
from fastapi.testclient import TestClient

from scentiq_api.config import Settings
from scentiq_api.main import create_app


def make_test_settings() -> Settings:
    return Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL="postgresql+psycopg://user:database-secret@private-db/scentiq_test",
        CORS_ORIGINS="http://localhost:5173",
    )


def test_request_log_contains_safe_http_metadata(caplog: pytest.LogCaptureFixture) -> None:
    settings = make_test_settings()
    app = create_app(settings, lambda: None)

    with caplog.at_level(logging.INFO, logger="scentiq_api.request"), TestClient(app) as client:
        response = client.request(
            "GET",
            "/health/live?token=do-not-log",
            headers={
                "Authorization": "Bearer authorization-secret",
                "Cookie": "session=cookie-secret",
            },
            content=b"request-body-secret",
        )

    assert response.status_code == 200
    request_records = [record for record in caplog.records if record.name == "scentiq_api.request"]
    assert len(request_records) == 1
    record = request_records[0]
    record_data = vars(record)
    assert cast(str, record_data["http_method"]) == "GET"
    assert cast(str, record_data["http_path"]) == "/health/live"
    assert cast(int, record_data["http_status"]) == 200
    assert cast(float, record_data["duration_ms"]) >= 0

    rendered_record = f"{record.getMessage()} {vars(record)!r}"
    for secret in (
        "token",
        "do-not-log",
        "request-body-secret",
        "DATABASE_URL",
        settings.database_url_value,
        "Authorization",
        "authorization-secret",
        "Cookie",
        "cookie-secret",
    ):
        assert secret not in rendered_record
