import pytest
from pydantic import ValidationError

from scentiq_api.config import Settings


@pytest.mark.parametrize("missing_field", ["SCENTIQ_ENV", "DATABASE_URL", "CORS_ORIGINS"])
def test_missing_required_settings_render_secret_safe_startup_errors(
    missing_field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    values = {
        "SCENTIQ_ENV": "test",
        "DATABASE_URL": "postgresql+psycopg://user:persistent-secret@private-db/scentiq",
        "CORS_ORIGINS": "http://localhost:3000",
    }
    for field in values:
        monkeypatch.delenv(field, raising=False)
    for field, value in values.items():
        if field != missing_field:
            monkeypatch.setenv(field, value)

    with pytest.raises(ValidationError) as error:
        Settings()

    for rendered_error in (str(error.value), repr(error.value)):
        assert missing_field in rendered_error
        assert "persistent-secret" not in rendered_error
        assert "private-db" not in rendered_error
        assert "input_value" not in rendered_error
        assert "input_type" not in rendered_error

    structured_errors = error.value.errors(include_input=False)
    assert all("input" not in detail for detail in structured_errors)
    assert "persistent-secret" not in repr(structured_errors)
    assert "private-db" not in repr(structured_errors)

    structured_json = error.value.json(include_input=False)
    assert '"input"' not in structured_json
    assert "persistent-secret" not in structured_json
    assert "private-db" not in structured_json


def test_settings_parse_safe_development_values() -> None:
    settings = Settings(
        SCENTIQ_ENV="development",
        DATABASE_URL="postgresql+psycopg://user:password@localhost/scentiq",
        CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000",
    )
    assert settings.environment == "development"
    assert settings.cors_origin_list == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_settings_normalize_development_resource_suffix() -> None:
    settings = Settings(
        SCENTIQ_ENV="dev",
        DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/scentiq",
        CORS_ORIGINS="http://localhost:3000",
    )

    assert settings.environment == "development"


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(
            SCENTIQ_ENV="production",
            DATABASE_URL="postgresql+psycopg://user:secret@db/scentiq",
            CORS_ORIGINS="*",
        )
    assert "wildcard" in str(error.value).lower()
    assert "secret" not in str(error.value)


def test_database_url_is_redacted_from_repr() -> None:
    settings = Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL="postgresql+psycopg://user:top-secret@db/scentiq",
        CORS_ORIGINS="http://localhost:3000",
    )
    assert "top-secret" not in repr(settings)
    assert settings.database_url_value.endswith("@db/scentiq")


@pytest.mark.parametrize(
    ("database_url", "sensitive_fragments"),
    [
        ("sqlite:///local.db", ("sqlite:///local.db",)),
        (
            "not-a-sqlalchemy-url:driver-secret@private-driver-host",
            ("driver-secret", "private-driver-host"),
        ),
        (
            "postgresql://user:driver-secret@private-driver-host/scentiq",
            ("driver-secret", "private-driver-host"),
        ),
        (
            "postgresql+asyncpg://user:driver-secret@private-driver-host/scentiq",
            ("driver-secret", "private-driver-host"),
        ),
        (
            "postgresql+psycopg://user:password@host:port-secret/db",
            ("password", "host", "port-secret"),
        ),
    ],
    ids=[
        "sqlite",
        "malformed",
        "plain-postgresql",
        "wrong-postgresql-driver",
        "malformed-exact-driver-port",
    ],
)
def test_database_url_rejects_invalid_or_non_psycopg_urls_without_rendering_input(
    database_url: str, sensitive_fragments: tuple[str, ...]
) -> None:
    with pytest.raises(ValidationError) as error:
        Settings(
            SCENTIQ_ENV="test",
            DATABASE_URL=database_url,
            CORS_ORIGINS="http://localhost:3000",
        )

    for rendered_error in (str(error.value), repr(error.value)):
        assert "valid postgresql+psycopg SQLAlchemy URL" in rendered_error
        assert database_url not in rendered_error
        assert "input_value" not in rendered_error
        assert "input_type" not in rendered_error
        for fragment in sensitive_fragments:
            assert fragment not in rendered_error

    structured_errors = error.value.errors(include_input=False)
    assert all("input" not in detail for detail in structured_errors)
    for fragment in sensitive_fragments:
        assert fragment not in repr(structured_errors)


def test_database_url_accepts_exact_postgresql_psycopg_driver() -> None:
    database_url = "postgresql+psycopg://user:password@localhost/scentiq"

    settings = Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL=database_url,
        CORS_ORIGINS="http://localhost:3000",
    )

    assert settings.database_url_value == database_url


def test_settings_reject_empty_cors_origin_list() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(
            SCENTIQ_ENV="development",
            DATABASE_URL="postgresql+psycopg://user:secret@db/scentiq",
            CORS_ORIGINS=" , ",
        )
    assert "must not be empty" in str(error.value).lower()
    assert "secret" not in str(error.value)
