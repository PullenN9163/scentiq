import base64
import binascii
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

Environment = Literal["development", "test", "production"]


def _decode_key(value: str) -> bytes:
    try:
        return base64.b64decode(value.strip(), validate=True)
    except binascii.Error, ValueError:
        return b""


DEFAULT_DEMO_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
# Open-Meteo's free endpoints. The commercial plan uses customer-* hosts plus an
# API key, so both are configurable rather than hard-coded.
DEFAULT_WEATHER_API_BASE_URL = "https://api.open-meteo.com"
DEFAULT_GEOCODING_API_BASE_URL = "https://geocoding-api.open-meteo.com"


class HybridWorkerSettings(BaseSettings):
    """Storage-only settings for the home worker's least-privilege runtime."""

    model_config = SettingsConfigDict(env_file=None, hide_input_in_errors=True)

    environment: Environment = Field(validation_alias="SCENTIQ_ENV")
    azure_storage_account_url: str = Field(validation_alias="AZURE_STORAGE_ACCOUNT_URL")

    @property
    def azure_storage_queue_account_url(self) -> str:
        if ".blob." not in self.azure_storage_account_url:
            raise RuntimeError("AZURE_STORAGE_ACCOUNT_URL must be an Azure Blob service URL")
        return self.azure_storage_account_url.replace(".blob.", ".queue.", 1)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, hide_input_in_errors=True)

    environment: Environment = Field(validation_alias="SCENTIQ_ENV")
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    cors_origins: str = Field(validation_alias="CORS_ORIGINS")
    demo_user_id: UUID = Field(default=DEFAULT_DEMO_USER_ID, validation_alias="DEMO_USER_ID")
    azure_client_id: str | None = Field(default=None, validation_alias="AZURE_CLIENT_ID")
    azure_storage_account_url: str | None = Field(
        default=None,
        validation_alias="AZURE_STORAGE_ACCOUNT_URL",
    )
    azure_key_vault_url: str | None = Field(
        default=None,
        validation_alias="AZURE_KEY_VAULT_URL",
    )
    applicationinsights_connection_string: SecretStr | None = Field(
        default=None,
        validation_alias="APPLICATIONINSIGHTS_CONNECTION_STRING",
    )
    clerk_issuer: str | None = Field(default=None, validation_alias="CLERK_ISSUER")
    clerk_jwks_url: str | None = Field(default=None, validation_alias="CLERK_JWKS_URL")
    clerk_audience: str | None = Field(default=None, validation_alias="CLERK_AUDIENCE")
    clerk_authorized_parties: str | None = Field(
        default=None,
        validation_alias="CLERK_AUTHORIZED_PARTIES",
    )
    internal_service_token: SecretStr | None = Field(
        default=None,
        validation_alias="INTERNAL_SERVICE_TOKEN",
    )
    weather_api_base_url: str = Field(
        default=DEFAULT_WEATHER_API_BASE_URL,
        validation_alias="WEATHER_API_BASE_URL",
    )
    geocoding_api_base_url: str = Field(
        default=DEFAULT_GEOCODING_API_BASE_URL,
        validation_alias="GEOCODING_API_BASE_URL",
    )
    open_meteo_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPEN_METEO_API_KEY",
    )
    public_app_url: str | None = Field(default=None, validation_alias="PUBLIC_APP_URL")
    google_oauth_client_id: str | None = Field(
        default=None, validation_alias="GOOGLE_OAUTH_CLIENT_ID"
    )
    google_oauth_client_secret: SecretStr | None = Field(
        default=None, validation_alias="GOOGLE_OAUTH_CLIENT_SECRET"
    )
    microsoft_oauth_client_id: str | None = Field(
        default=None, validation_alias="MICROSOFT_OAUTH_CLIENT_ID"
    )
    microsoft_oauth_client_secret: SecretStr | None = Field(
        default=None, validation_alias="MICROSOFT_OAUTH_CLIENT_SECRET"
    )
    integration_token_encryption_key: SecretStr | None = Field(
        default=None, validation_alias="INTEGRATION_TOKEN_ENCRYPTION_KEY"
    )
    integration_token_previous_keys: SecretStr | None = Field(
        default=None, validation_alias="INTEGRATION_TOKEN_PREVIOUS_KEYS"
    )
    hybrid_catalog_version: str = Field(
        default="catalog-v1", validation_alias="HYBRID_CATALOG_VERSION"
    )
    hybrid_algorithm_version: str = Field(default="v1", validation_alias="HYBRID_ALGORITHM_VERSION")
    recommendation_max_age_seconds: int = Field(
        default=21600,
        gt=0,
        validation_alias="RECOMMENDATION_MAX_AGE_SECONDS",
    )

    @field_validator(
        "clerk_issuer",
        "clerk_jwks_url",
        "clerk_audience",
        "clerk_authorized_parties",
        "internal_service_token",
        "open_meteo_api_key",
        "public_app_url",
        "google_oauth_client_id",
        "google_oauth_client_secret",
        "microsoft_oauth_client_id",
        "microsoft_oauth_client_secret",
        "integration_token_encryption_key",
        "integration_token_previous_keys",
        mode="before",
    )
    @classmethod
    def treat_blank_as_unset(cls, value: object) -> object:
        """Read a blank optional setting as absent rather than as a value.

        Deployment templates supply every declared variable, so an unconfigured
        setting arrives as an empty string instead of being omitted. Without
        this, an empty CLERK_AUDIENCE reads as a real audience of "", which
        turns audience verification on and rejects every token.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "google_oauth_client_id",
        "google_oauth_client_secret",
        "microsoft_oauth_client_id",
        "microsoft_oauth_client_secret",
    )
    @classmethod
    def strip_oauth_credentials(cls, value: str | SecretStr | None) -> str | SecretStr | None:
        """Drop surrounding whitespace from OAuth client credentials.

        A secret pasted or piped into Key Vault easily picks up a trailing
        newline, and the provider then rejects the client as `invalid_client`
        even though the value looks right.
        """
        if isinstance(value, SecretStr):
            return SecretStr(value.get_secret_value().strip())
        return value.strip() if isinstance(value, str) else value

    @field_validator("weather_api_base_url", mode="before")
    @classmethod
    def default_weather_api_base_url(cls, value: object) -> object:
        """A blank or missing URL means the free public endpoint."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return DEFAULT_WEATHER_API_BASE_URL
        return value

    @field_validator("geocoding_api_base_url", mode="before")
    @classmethod
    def default_geocoding_api_base_url(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return DEFAULT_GEOCODING_API_BASE_URL
        return value

    @field_validator("weather_api_base_url", "geocoding_api_base_url")
    @classmethod
    def validate_weather_urls(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("Weather provider URLs must be https URLs")
        return value.rstrip("/")

    @field_validator("public_app_url")
    @classmethod
    def validate_public_app_url(cls, value: str | None) -> str | None:
        """The browser-facing origin; OAuth providers redirect back to it.

        Plain http is accepted only for local development hosts.
        """
        if value is None:
            return None
        url = value.rstrip("/")
        local = url.startswith(("http://localhost", "http://127.0.0.1"))
        if not url.startswith("https://") and not local:
            raise ValueError("PUBLIC_APP_URL must be an https URL")
        return url

    @field_validator("integration_token_encryption_key", "integration_token_previous_keys")
    @classmethod
    def validate_encryption_keys(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        for candidate in value.get_secret_value().split(","):
            if len(_decode_key(candidate)) != 32:
                raise ValueError("Integration token encryption keys must be 32 base64 bytes")
        return value

    @field_validator("clerk_issuer")
    @classmethod
    def validate_clerk_issuer(cls, value: str | None) -> str | None:
        if value is None:
            return None
        issuer = value.rstrip("/")
        if not issuer.startswith("https://"):
            raise ValueError("CLERK_ISSUER must be an https URL")
        return issuer

    @field_validator("clerk_jwks_url")
    @classmethod
    def validate_clerk_jwks_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.startswith("https://"):
            raise ValueError("CLERK_JWKS_URL must be an https URL")
        return value

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_environment(cls, value: object) -> object:
        return "development" if value == "dev" else value

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value: object) -> object:
        if isinstance(value, SecretStr):
            candidate: str | URL = value.get_secret_value()
        elif isinstance(value, (str, URL)):
            candidate = value
        else:
            raise ValueError("DATABASE_URL must be a valid postgresql+psycopg SQLAlchemy URL")

        try:
            parsed_url = make_url(candidate)
        except ArgumentError, ValueError:
            raise ValueError(
                "DATABASE_URL must be a valid postgresql+psycopg SQLAlchemy URL"
            ) from None

        if parsed_url.drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must be a valid postgresql+psycopg SQLAlchemy URL")

        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str, info: ValidationInfo) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS origin list must not be empty")
        if info.data.get("environment") == "production" and "*" in origins:
            raise ValueError("Wildcard CORS origins are not allowed in production")
        return value

    @property
    def database_url_value(self) -> str:
        return self.database_url.get_secret_value()

    @property
    def azure_storage_queue_account_url(self) -> str:
        if self.azure_storage_account_url is None:
            raise RuntimeError("AZURE_STORAGE_ACCOUNT_URL is not configured")
        if ".blob." not in self.azure_storage_account_url:
            raise RuntimeError("AZURE_STORAGE_ACCOUNT_URL must be an Azure Blob service URL")
        return self.azure_storage_account_url.replace(".blob.", ".queue.", 1)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def applicationinsights_connection_string_value(self) -> str | None:
        if self.applicationinsights_connection_string is None:
            return None
        return self.applicationinsights_connection_string.get_secret_value()

    @property
    def resolved_clerk_jwks_url(self) -> str | None:
        """Explicit JWKS URL, otherwise the issuer's well-known location."""
        if self.clerk_jwks_url is not None:
            return self.clerk_jwks_url
        if self.clerk_issuer is not None:
            return f"{self.clerk_issuer}/.well-known/jwks.json"
        return None

    @property
    def clerk_authorized_party_list(self) -> list[str]:
        if self.clerk_authorized_parties is None:
            return []
        return [
            party.strip() for party in self.clerk_authorized_parties.split(",") if party.strip()
        ]

    @property
    def authentication_is_configured(self) -> bool:
        """Authentication fails closed until an issuer and JWKS source exist."""
        return self.clerk_issuer is not None and self.resolved_clerk_jwks_url is not None

    @property
    def open_meteo_api_key_value(self) -> str | None:
        if self.open_meteo_api_key is None:
            return None
        return self.open_meteo_api_key.get_secret_value()

    @property
    def integration_token_keys(self) -> list[bytes]:
        """The current key first, then any previous keys still accepted."""
        keys: list[bytes] = []
        for secret in (self.integration_token_encryption_key, self.integration_token_previous_keys):
            if secret is None:
                continue
            keys.extend(
                _decode_key(candidate)
                for candidate in secret.get_secret_value().split(",")
                if candidate.strip()
            )
        return keys

    @property
    def google_oauth_client_secret_value(self) -> str | None:
        if self.google_oauth_client_secret is None:
            return None
        return self.google_oauth_client_secret.get_secret_value()

    @property
    def microsoft_oauth_client_secret_value(self) -> str | None:
        if self.microsoft_oauth_client_secret is None:
            return None
        return self.microsoft_oauth_client_secret.get_secret_value()

    @property
    def internal_service_token_value(self) -> str | None:
        if self.internal_service_token is None:
            return None
        return self.internal_service_token.get_secret_value()
