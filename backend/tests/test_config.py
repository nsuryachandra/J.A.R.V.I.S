"""Unit tests for Settings and environment validation."""

import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_default_settings():
    """Verify system defaults adhere to PRD specifications."""
    settings = Settings()
    assert settings.app_name == "JARVIS"
    assert settings.timezone == "Asia/Kolkata"
    assert settings.environment == "development"
    assert settings.is_sqlite is True
    assert settings.is_production is False
    assert isinstance(settings.allowed_origins, list)


def test_invalid_timezone_rejected():
    """Verify that an invalid IANA timezone string raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(timezone="Invalid/NonExistent_Zone")
    assert "Invalid IANA timezone" in str(exc_info.value)


def test_valid_custom_timezone():
    """Verify valid alternative IANA timezone is accepted."""
    settings = Settings(timezone="UTC")
    assert settings.timezone == "UTC"


def test_allowed_origins_string_parsing():
    """Verify comma-separated origins string parses into clean list."""
    settings = Settings(allowed_origins="http://localhost:3000, https://myapp.com ")
    assert settings.allowed_origins == ["http://localhost:3000", "https://myapp.com"]


def test_environment_validation():
    """Verify that only recognized deployment environments are permitted."""
    valid_envs = ["development", "testing", "staging", "production"]
    for env in valid_envs:
        s = Settings(environment=env)
        assert s.environment == env

    with pytest.raises(ValidationError):
        Settings(environment="unknown_env")
