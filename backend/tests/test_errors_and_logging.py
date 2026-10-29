"""Verify safe errors and basic log redaction."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from opsbridge.infrastructure.config import Settings
from opsbridge.infrastructure.observability import JsonFormatter
from opsbridge.presentation.http.app import create_app


def test_unhandled_error_does_not_expose_exception_text(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite+pysqlite:///{(tmp_path / 'errors.db').as_posix()}",
    )
    application: FastAPI = create_app(settings)

    @application.get("/_test/unhandled")
    async def fail() -> None:
        raise RuntimeError("password=not-for-the-response")

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/_test/unhandled")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "INTERNAL_SERVER_ERROR"
    assert "not-for-the-response" not in response.text
    assert "traceback" not in response.text.lower()


def test_json_formatter_redacts_common_secret_forms() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="password=hunter2 authorization=Bearer abc.def token='value'",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)

    assert "hunter2" not in formatted
    assert "abc.def" not in formatted
    assert "'value'" not in formatted
    assert formatted.count("[REDACTED]") == 3
