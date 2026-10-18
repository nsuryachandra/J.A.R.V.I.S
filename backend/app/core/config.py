"""Application configuration and environment validation using Pydantic Settings."""

import zoneinfo
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """JARVIS system configuration with strict type validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core Application Settings
    app_name: str = Field(default="JARVIS", description="Application service name")
    environment: str = Field(
        default="development",
        description="Deployment environment (development, testing, staging, production)",
    )
    log_level: str = Field(default="INFO", description="Standard logging level")
    app_secret_key: str = Field(
        default="dev-insecure-secret-key-at-least-32-characters-long",
        description="Server-side secret key for cryptographic token signing",
    )
    timezone: str = Field(
        default="Asia/Kolkata",
        description="Default localized user timezone",
    )
    port: int = Field(default=8000, description="Listening port for FastAPI server")
    host: str = Field(default="0.0.0.0", description="Listening host interface")

    # Security & Authentication Settings
    password_hashing_algorithm: str = Field(
        default="argon2id",
        description="Preferred password hashing algorithm ('argon2id' or 'bcrypt')",
    )
    access_token_expire_minutes: int = Field(
        default=15,
        description="Access token lifespan in minutes",
    )
    refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh token lifespan in days",
    )
    approval_expire_seconds: int = Field(
        default=300,
        description="Consequential action approval expiration window in seconds (default 5 min)",
    )

    # Database Settings
    # Default is SQLite with async driver for zero-dependency local development and tests
    database_url: str = Field(
        default="sqlite+aiosqlite:///./jarvis_dev.db",
        description="Async database connection string (PostgreSQL or SQLite)",
    )
    database_pool_size: int = Field(default=5, description="Connection pool size")
    database_max_overflow: int = Field(
        default=10, description="Max overflow connections beyond pool size"
    )

    # CORS Settings
    allowed_origins: Union[List[str], str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origin domains or comma-separated string",
    )

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate that the timezone string is recognized by IANA."""
        try:
            zoneinfo.ZoneInfo(v)
        except Exception as exc:
            raise ValueError(f"Invalid IANA timezone '{v}': {exc}") from exc
        return v

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse comma-separated origin string into list of strings."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "testing", "staging", "production"}
        norm = v.lower()
        if norm not in allowed:
            raise ValueError(f"Environment '{v}' must be one of {allowed}")
        return norm

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_testing(self) -> bool:
        return self.environment == "testing"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


# Global singleton settings factory
_settings: Settings | None = None


def get_settings() -> Settings:
    """Retrieve cached global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
