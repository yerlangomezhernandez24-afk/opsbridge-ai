"""Minimal structured logging with conservative field selection and redaction."""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(password|token|secret)\b\s*[=:]\s*(?:\"[^\"]*\"|'[^']*'|\S+)"
)
_AUTHORIZATION_ASSIGNMENT = re.compile(
    r"(?i)\bauthorization\b\s*[=:]\s*(?:bearer\s+)?(?:\"[^\"]*\"|'[^']*'|\S+)"
)
_BEARER_VALUE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_SAFE_EXTRA_FIELDS = (
    "event",
    "correlation_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
)


def redact(value: str) -> str:
    """Redact common credential forms before a log record is serialized."""

    value = _AUTHORIZATION_ASSIGNMENT.sub("authorization=[REDACTED]", value)
    value = _SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    return _BEARER_VALUE.sub("Bearer [REDACTED]", value)


class JsonFormatter(logging.Formatter):
    """Emit a stable JSON object and ignore arbitrary record extras."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        for field_name in _SAFE_EXTRA_FIELDS:
            field_value = getattr(record, field_name, None)
            if field_value is not None:
                payload[field_name] = field_value
        if record.exc_info:
            exception_type = record.exc_info[0]
            if exception_type is not None:
                payload["exception"] = exception_type.__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> None:
    """Configure one stderr handler without logging application settings."""

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
