import io
import json
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


def test_runtime_logging_replaces_unsafe_access_log_with_safe_output() -> None:
    settings = make_test_settings()
    app = create_app(settings, lambda: None)
    access_logger = logging.getLogger("uvicorn.access")
    original_disabled = access_logger.disabled
    access_logger.disabled = False

    try:
        with TestClient(app) as client:
            request_logger = logging.getLogger("scentiq_api.request")
            request_handler = next(
                handler
                for handler in request_logger.handlers
                if handler.get_name() == "scentiq-runtime-request"
            )
            assert isinstance(request_handler, logging.StreamHandler)
            runtime_stream = io.StringIO()
            original_stream = request_handler.setStream(runtime_stream)
            try:
                response = client.request(
                    "GET",
                    "/health/live?token=runtime-query-secret",
                    headers={
                        "Authorization": "Bearer runtime-authorization-secret",
                        "Cookie": "session=runtime-cookie-secret",
                    },
                    content=b"runtime-body-secret",
                )
            finally:
                request_handler.setStream(original_stream)

        assert response.status_code == 200
        assert access_logger.disabled is True
        runtime_output = runtime_stream.getvalue()
        payload = json.loads(runtime_output)
        assert payload["event"] == "http_request_completed"
        assert payload["level"] == "INFO"
        assert payload["method"] == "GET"
        assert payload["path"] == "/health/live"
        assert payload["status"] == 200
        assert payload["duration_ms"] >= 0
        for secret in (
            "token",
            "runtime-query-secret",
            "runtime-authorization-secret",
            "runtime-cookie-secret",
            "runtime-body-secret",
            settings.database_url_value,
        ):
            assert secret not in runtime_output
    finally:
        access_logger.disabled = original_disabled


def test_runtime_logging_escapes_decoded_path_control_characters() -> None:
    settings = make_test_settings()
    app = create_app(settings, lambda: None)

    with TestClient(app) as client:
        request_logger = logging.getLogger("scentiq_api.request")
        request_handler = next(
            handler
            for handler in request_logger.handlers
            if handler.get_name() == "scentiq-runtime-request"
        )
        assert isinstance(request_handler, logging.StreamHandler)
        runtime_stream = io.StringIO()
        original_stream = request_handler.setStream(runtime_stream)
        try:
            response = client.request(
                "GET",
                "/health/live/%0AINFO%3A%20forged%1B%5B31m%7F?token=path-query-secret",
                headers={
                    "Authorization": "Bearer path-authorization-secret",
                    "Cookie": "session=path-cookie-secret",
                },
                content=b"path-body-secret",
            )
        finally:
            request_handler.setStream(original_stream)

    assert response.status_code == 404
    runtime_output = runtime_stream.getvalue()
    assert runtime_output.count("\n") == 1
    physical_record = runtime_output.rstrip("\n")
    assert not any(ord(character) < 32 or ord(character) == 127 for character in physical_record)
    assert "\x1b" not in physical_record

    payload = json.loads(physical_record)
    assert payload == {
        "duration_ms": payload["duration_ms"],
        "event": "http_request_completed",
        "level": "INFO",
        "method": "GET",
        "path": "/health/live/\nINFO: forged\x1b[31m\x7f",
        "status": 404,
    }
    assert payload["duration_ms"] >= 0
    for secret in (
        "token",
        "path-query-secret",
        "path-authorization-secret",
        "path-cookie-secret",
        "path-body-secret",
        settings.database_url_value,
    ):
        assert secret not in runtime_output
