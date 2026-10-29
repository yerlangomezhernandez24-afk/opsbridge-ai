"""Configuration defaults and fail-closed validation."""

import pytest
from pydantic import ValidationError

from opsbridge.infrastructure.config import Settings


def test_default_configuration_is_local_and_non_debug() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.debug is False
    assert settings.database_url.startswith("sqlite+pysqlite:///")


@pytest.mark.parametrize(
    "host",
    ["0.0.0.0", "192.168.1.20", "example.com"],  # noqa: S104 - rejection cases
)
def test_non_loopback_host_is_rejected(host: str) -> None:
    with pytest.raises(ValidationError, match="loopback"):
        Settings(_env_file=None, host=host)


def test_non_sqlite_database_is_rejected() -> None:
    with pytest.raises(ValidationError, match="SQLite"):
        Settings(_env_file=None, database_url="postgresql://example.invalid/opsbridge")


def test_debug_is_rejected_outside_test_environment() -> None:
    with pytest.raises(ValidationError, match="test environment"):
        Settings(_env_file=None, debug=True)


def test_frontend_origin_must_be_exact_loopback() -> None:
    with pytest.raises(ValidationError, match="loopback"):
        Settings(_env_file=None, frontend_origin="https://example.com")
    with pytest.raises(ValidationError, match="exact HTTP"):
        Settings(_env_file=None, frontend_origin="http://127.0.0.1:5173/path")


def test_session_durations_and_secure_cookie_configuration_are_validated() -> None:
    with pytest.raises(ValidationError, match="idle duration"):
        Settings(
            _env_file=None,
            session_absolute_minutes=15,
            session_idle_minutes=30,
        )
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(_env_file=None, session_cookie_secure=True)
