"""Environment-backed application settings."""

import json
from functools import lru_cache
from typing import Any

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        enable_decoding=False,
        extra="ignore",
    )

    app_name: str = "snapstream"
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"),
    )
    debug: bool = False
    database_url: str = "postgresql+asyncpg://snapstream:snapstream@localhost:5432/snapstream"
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, ge=60, le=60 * 60 * 24 * 365)
    feed_cache_ttl_seconds: int = Field(default=15, ge=1, le=3600)
    s3_bucket: str = ""
    s3_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("AWS_REGION", "S3_REGION"),
    )
    s3_endpoint_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AWS_ENDPOINT_URL", "S3_ENDPOINT_URL"),
    )
    s3_object_base_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: SecretStr | None = None
    upload_url_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    max_media_size_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1,
        le=5 * 1024**3,
        validation_alias=AliasChoices("MAX_UPLOAD_BYTES", "MAX_MEDIA_SIZE_BYTES"),
    )
    allowed_media_types: tuple[str, ...] = (
        "image/jpeg",
        "image/png",
        "image/webp",
        "video/mp4",
        "video/quicktime",
        "video/webm",
    )
    cors_origins: list[str] = ["*"]

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Use the async PostgreSQL driver for conventional deployment URLs."""
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @field_validator("s3_endpoint_url", mode="before")
    @classmethod
    def empty_string_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("allowed_media_types", mode="before")
    @classmethod
    def parse_media_types(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return tuple(value)  # type: ignore[arg-type]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if not isinstance(value, str):
            return list(value)
        if value.lstrip().startswith("["):
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise ValueError("CORS_ORIGINS must be a JSON list or comma-separated string")
            return [str(item) for item in parsed]
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
