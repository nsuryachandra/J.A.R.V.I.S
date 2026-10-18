"""Application configuration and environment validation using Pydantic Settings."""

import zoneinfo
from typing import List, Optional, Union
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

    # NVIDIA NIM & Model Strategy Settings
    nvidia_api_key: Optional[str] = Field(
        default=None,
        description="NVIDIA NIM API key for live inference",
    )
    nvidia_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        description="NVIDIA NIM API base URL",
    )
    model_fast_chat: str = Field(
        default="meta/llama-3.1-8b-instruct",
        description="Default model for fast chat, greetings, and simple interactions",
    )
    model_reasoning: str = Field(
        default="meta/llama-3.1-70b-instruct",
        description="Default model for complex multi-step planning and deep reasoning",
    )
    model_coding: str = Field(
        default="meta/llama-3.1-70b-instruct",
        description="Default model for code analysis, refactoring, and generation",
    )
    model_vision: str = Field(
        default="nvidia/neva-22b",
        description="Default model for multimodal and image inspection",
    )
    model_embedding: str = Field(
        default="nvidia/nv-embed-v1",
        description="Default model for semantic text embeddings",
    )
    model_timeout_seconds: int = Field(
        default=30,
        description="HTTP timeout in seconds for model inference calls",
    )
    model_max_retries: int = Field(
        default=2,
        description="Maximum exponential backoff retries for failed model calls",
    )
    use_mock_models: bool = Field(
        default=True,
        description="Whether to use mock provider when live API key is missing or offline",
    )

    # ElevenLabs & Voice System Settings
    elevenlabs_api_key: Optional[str] = Field(
        default=None,
        description="ElevenLabs API key for live speech synthesis",
    )
    elevenlabs_base_url: str = Field(
        default="https://api.elevenlabs.io/v1",
        description="ElevenLabs API base URL",
    )
    elevenlabs_default_voice_id: str = Field(
        default="21m00Tcm4TlvDq8ikWAM",
        description="Default voice ID (Rachel / Neutral Multilingual)",
    )
    elevenlabs_model_id: str = Field(
        default="eleven_multilingual_v2",
        description="Default ElevenLabs TTS model identifier",
    )
    voice_timeout_seconds: int = Field(
        default=30,
        description="HTTP timeout in seconds for voice generation",
    )
    use_mock_voice: bool = Field(
        default=True,
        description="Whether to use mock voice provider when API key is missing or in tests",
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
