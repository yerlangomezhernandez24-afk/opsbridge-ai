"""Validated application settings loaded from environment variables."""

from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIRECTORY = Path(__file__).resolve().parents[3]
_DEFAULT_DATABASE = (_BACKEND_DIRECTORY / "var" / "opsbridge.db").as_posix()


class Settings(BaseSettings):
    """Fail-closed settings for the local backend."""

    model_config = SettingsConfigDict(
        env_prefix="OPSBRIDGE_",
        env_file=_BACKEND_DIRECTORY / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )

    environment: Literal["development", "test"] = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1024, le=65535)
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str = f"sqlite+pysqlite:///{_DEFAULT_DATABASE}"
    frontend_origin: str = "http://127.0.0.1:5173"
    session_cookie_secure: bool = False
    session_absolute_minutes: int = Field(default=480, ge=15, le=1440)
    session_idle_minutes: int = Field(default=30, ge=5, le=240)

    @field_validator("host")
    @classmethod
    def host_must_be_loopback(cls, value: str) -> str:
        """Prevent accidental network exposure in the local demo profile."""

        normalized = value.strip().lower()
        if normalized == "localhost":
            return normalized
        try:
            address = ip_address(normalized)
        except ValueError as exc:
            raise ValueError("host must be localhost or a loopback IP address") from exc
        if not address.is_loopback:
            raise ValueError("host must be a loopback IP address")
        return normalized

    @field_validator("database_url")
    @classmethod
    def database_must_be_sqlite(cls, value: str) -> str:
        """Restrict the current local profile to SQLite until another adapter is reviewed."""

        if not value.startswith(("sqlite://", "sqlite+pysqlite://")):
            raise ValueError("only SQLite database URLs are supported in Phase 2.0")
        return value

    @field_validator("frontend_origin")
    @classmethod
    def frontend_origin_must_be_exact_loopback(cls, value: str) -> str:
        """Allow one explicit local origin, never a wildcard or URL prefix."""

        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("frontend_origin must be an exact HTTP(S) origin")
        try:
            is_loopback = ip_address(parsed.hostname).is_loopback
        except ValueError:
            is_loopback = parsed.hostname.lower() == "localhost"
        if not is_loopback:
            raise ValueError("frontend_origin must use a loopback host")
        return value.rstrip("/")

    @model_validator(mode="after")
    def debug_is_test_only(self) -> Self:
        """Avoid exposing debug behavior in the default development profile."""

        if self.debug and self.environment != "test":
            raise ValueError("debug may only be enabled in the test environment")
        if self.session_idle_minutes > self.session_absolute_minutes:
            raise ValueError("session idle duration cannot exceed absolute duration")
        if self.session_cookie_secure and not self.frontend_origin.startswith("https://"):
            raise ValueError("secure cookies require an HTTPS frontend origin")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one validated settings object per process."""

    return Settings()
