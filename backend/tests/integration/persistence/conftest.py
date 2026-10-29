"""Isolated real-file SQLite fixtures."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from opsbridge.infrastructure.db import Base, Database


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    path = tmp_path / "opsbridge-test.db"
    instance = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(instance.engine)
    try:
        yield instance
    finally:
        instance.dispose()
