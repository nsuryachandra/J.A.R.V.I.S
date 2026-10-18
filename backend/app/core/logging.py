"""Structured logging configuration with automated secret masking."""

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict

# Patterns for sensitive keys and sensitive tokens
SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|secret|token|api_key|apikey|authorization|bearer|private_key|cookie)",
    re.IGNORECASE,
)
SENSITIVE_VALUE_PATTERN = re.compile(
    r"(Bearer\s+)[A-Za-z0-9_\-\.]{10,}|(nvapi-[A-Za-z0-9_\-]{20,})|([A-Za-z0-9]{32,})",
    re.IGNORECASE,
)
MASK = "***MASKED***"


def mask_sensitive_data(obj: Any) -> Any:
    """Recursively mask sensitive values in dictionaries, lists, or strings."""
    if isinstance(obj, dict):
        masked_dict = {}
        for k, v in obj.items():
            if SENSITIVE_KEY_PATTERN.search(str(k)):
                masked_dict[k] = MASK
            else:
                masked_dict[k] = mask_sensitive_data(v)
        return masked_dict
    elif isinstance(obj, list):
        return [mask_sensitive_data(item) for item in obj]
    elif isinstance(obj, str):
        # Mask matching regex patterns within strings
        return SENSITIVE_VALUE_PATTERN.sub(r"\1" + MASK, obj)
    return obj


class MaskingLogRecord(logging.LogRecord):
    """LogRecord that automatically masks sensitive information in the message."""

    def getMessage(self) -> str:
        msg = super().getMessage()
        return SENSITIVE_VALUE_PATTERN.sub(r"\1" + MASK, msg)


class JSONFormatter(logging.Formatter):
    """Formats log records as newline-delimited JSON with ISO timestamps and masked secrets."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        # Clean sensitive patterns from message text
        masked_message = SENSITIVE_VALUE_PATTERN.sub(r"\1" + MASK, message)

        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": masked_message,
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Include custom extra attributes if present
        extra_attrs = getattr(record, "extra", {})
        if extra_attrs and isinstance(extra_attrs, dict):
            payload["extra"] = mask_sensitive_data(extra_attrs)

        return json.dumps(payload)


class SecretMaskingFilter(logging.Filter):
    """Logging filter ensuring all arguments and records are sanitized."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = SENSITIVE_VALUE_PATTERN.sub(r"\1" + MASK, record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = mask_sensitive_data(record.args)
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(mask_sensitive_data(a) for a in record.args)
        return True


def setup_logging(log_level: str = "INFO", json_output: bool = True) -> logging.Logger:
    """Configure system-wide root logger with secret masking."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.addFilter(SecretMaskingFilter())

    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        standard_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        handler.setFormatter(logging.Formatter(standard_format))

    root_logger.addHandler(handler)

    # Silence overly verbose external loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logging.getLogger("jarvis")
