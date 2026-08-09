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
