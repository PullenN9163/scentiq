from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

Environment = Literal["development", "test", "production"]
DEFAULT_DEMO_USER_ID = UUID("00000000-0000-4000-8000-000000000001")


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

    @field_validator(
        "clerk_issuer",
        "clerk_jwks_url",
        "clerk_audience",
        "clerk_authorized_parties",
        "internal_service_token",
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
    def internal_service_token_value(self) -> str | None:
        if self.internal_service_token is None:
            return None
        return self.internal_service_token.get_secret_value()
