import pytest
from pydantic import ValidationError

from scentiq_api.config import Settings


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


def test_settings_reject_empty_cors_origin_list() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(
            SCENTIQ_ENV="development",
            DATABASE_URL="postgresql+psycopg://user:secret@db/scentiq",
            CORS_ORIGINS=" , ",
        )
    assert "must not be empty" in str(error.value).lower()
    assert "secret" not in str(error.value)
