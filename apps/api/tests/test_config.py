import base64
from typing import Any

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


def test_blank_clerk_settings_are_treated_as_unset() -> None:
    """A deployment template supplies every variable, so unset arrives as "".

    An empty audience previously read as a real audience of "", which switched
    audience verification on and rejected every token.
    """
    settings = Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL="postgresql+psycopg://user:password@localhost/scentiq",
        CORS_ORIGINS="http://localhost:3000",
        CLERK_ISSUER="https://clerk.example.dev",
        CLERK_AUDIENCE="",
        CLERK_JWKS_URL="",
        CLERK_AUTHORIZED_PARTIES="   ",
        INTERNAL_SERVICE_TOKEN="",
    )

    assert settings.clerk_audience is None
    assert settings.clerk_jwks_url is None
    assert settings.clerk_authorized_parties is None
    assert settings.internal_service_token is None
    assert settings.clerk_authorized_party_list == []
    # A blank JWKS URL still falls back to the issuer's well-known location.
    assert settings.resolved_clerk_jwks_url == "https://clerk.example.dev/.well-known/jwks.json"
    assert settings.authentication_is_configured is True


def test_blank_issuer_leaves_authentication_unconfigured() -> None:
    settings = Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL="postgresql+psycopg://user:password@localhost/scentiq",
        CORS_ORIGINS="http://localhost:3000",
        CLERK_ISSUER="",
    )

    assert settings.clerk_issuer is None
    assert settings.authentication_is_configured is False


def test_blank_weather_settings_fall_back_to_the_free_endpoints() -> None:
    settings = Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL="postgresql+psycopg://user:password@localhost/scentiq",
        CORS_ORIGINS="http://localhost:3000",
        WEATHER_API_BASE_URL="",
        GEOCODING_API_BASE_URL="  ",
        OPEN_METEO_API_KEY="",
    )

    assert settings.weather_api_base_url == "https://api.open-meteo.com"
    assert settings.geocoding_api_base_url == "https://geocoding-api.open-meteo.com"
    assert settings.open_meteo_api_key_value is None


def test_commercial_weather_settings_are_accepted() -> None:
    settings = Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL="postgresql+psycopg://user:password@localhost/scentiq",
        CORS_ORIGINS="http://localhost:3000",
        WEATHER_API_BASE_URL="https://customer-api.open-meteo.com/",
        OPEN_METEO_API_KEY="commercial-key",
    )

    assert settings.weather_api_base_url == "https://customer-api.open-meteo.com"
    assert settings.open_meteo_api_key_value == "commercial-key"
    assert "commercial-key" not in repr(settings)


def test_weather_urls_must_be_https() -> None:
    with pytest.raises(ValidationError):
        Settings(
            SCENTIQ_ENV="test",
            DATABASE_URL="postgresql+psycopg://user:password@localhost/scentiq",
            CORS_ORIGINS="http://localhost:3000",
            WEATHER_API_BASE_URL="http://api.open-meteo.com",
        )


def _calendar_settings(**values: Any) -> Settings:
    return Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL="postgresql+psycopg://user:password@localhost/scentiq",
        CORS_ORIGINS="http://localhost:3000",
        **values,
    )


def test_calendar_settings_default_to_unconfigured() -> None:
    settings = _calendar_settings(
        PUBLIC_APP_URL="",
        GOOGLE_OAUTH_CLIENT_ID="",
        GOOGLE_OAUTH_CLIENT_SECRET="",
        INTEGRATION_TOKEN_ENCRYPTION_KEY="",
    )

    assert settings.public_app_url is None
    assert settings.google_oauth_client_id is None
    assert settings.google_oauth_client_secret_value is None
    assert settings.integration_token_keys == []


def test_encryption_keys_are_decoded_current_first() -> None:
    current, previous = bytes(range(32)), bytes(range(1, 33))
    settings = _calendar_settings(
        INTEGRATION_TOKEN_ENCRYPTION_KEY=base64.b64encode(current).decode(),
        INTEGRATION_TOKEN_PREVIOUS_KEYS=base64.b64encode(previous).decode(),
    )

    assert settings.integration_token_keys == [current, previous]


def test_a_short_encryption_key_is_rejected_without_echoing_it() -> None:
    with pytest.raises(ValidationError) as error:
        _calendar_settings(INTEGRATION_TOKEN_ENCRYPTION_KEY="c2hvcnQta2V5")
    assert "c2hvcnQta2V5" not in str(error.value)


@pytest.mark.parametrize(
    ("value", "accepted"),
    [
        ("https://scentiq.example.com/", True),
        ("http://localhost:3000", True),
        ("http://scentiq.example.com", False),
    ],
)
def test_public_app_url_requires_https_outside_local_development(
    value: str, accepted: bool
) -> None:
    if accepted:
        assert _calendar_settings(PUBLIC_APP_URL=value).public_app_url == value.rstrip("/")
    else:
        with pytest.raises(ValidationError):
            _calendar_settings(PUBLIC_APP_URL=value)
