"""Shared test application with an isolated temporary SQLite database."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from opsbridge.infrastructure.config import Settings
from opsbridge.infrastructure.db import Base
from opsbridge.presentation.http.app import create_app


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    database_path = tmp_path / "opsbridge-test.db"
    return Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite+pysqlite:///{database_path.as_posix()}",
    )


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    application = create_app(test_settings)
    Base.metadata.create_all(application.state.database.engine)
    with TestClient(application) as test_client:
        yield test_client
