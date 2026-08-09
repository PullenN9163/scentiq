from typing import Literal

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None)

    environment: Environment = Field(validation_alias="SCENTIQ_ENV")
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    cors_origins: str = Field(validation_alias="CORS_ORIGINS")
    azure_client_id: str | None = Field(default=None, validation_alias="AZURE_CLIENT_ID")
    azure_storage_account_url: str | None = Field(
        default=None,
        validation_alias="AZURE_STORAGE_ACCOUNT_URL",
    )
    azure_key_vault_url: str | None = Field(
        default=None,
        validation_alias="AZURE_KEY_VAULT_URL",
    )

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
