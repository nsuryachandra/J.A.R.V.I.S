"""Tests verifying that structured logging strictly masks sensitive secrets."""

import json
import logging
from app.core.logging import JSONFormatter, SecretMaskingFilter, mask_sensitive_data


def test_mask_sensitive_dict_data():
    """Verify recursive dictionary masking replaces sensitive values."""
    data = {
        "user": "surya",
        "api_key": "secret-nvapi-key-12345",
        "password": "plain-password-123",
        "token": "bearer-jwt-token-val",
        "nested": {
            "auth_token": "nested-token",
            "safe_field": "visible",
        },
    }
    masked = mask_sensitive_data(data)
    assert masked["user"] == "surya"
    assert masked["api_key"] == "***MASKED***"
    assert masked["password"] == "***MASKED***"
    assert masked["token"] == "***MASKED***"
    assert masked["nested"]["auth_token"] == "***MASKED***"
    assert masked["nested"]["safe_field"] == "visible"


def test_json_formatter_masks_bearer_and_secrets():
    """Verify JSONFormatter sanitizes Bearer tokens in formatted JSON strings."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Calling external endpoint with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz and nvapi-123456789012345678901234567890",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert "level" in parsed
    assert "timestamp" in parsed
    assert "***MASKED***" in parsed["message"]
    assert "nvapi-123456789012345678901234567890" not in parsed["message"]
