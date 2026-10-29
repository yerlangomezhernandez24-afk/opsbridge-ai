"""Concrete transaction and rollback behavior using a temporary database."""

from pathlib import Path

import pytest
from sqlalchemy import text

from opsbridge.infrastructure.db import Database


def test_session_commits_and_rolls_back(tmp_path: Path) -> None:
    database_path = tmp_path / "transaction-test.db"
    database = Database(f"sqlite+pysqlite:///{database_path.as_posix()}")
    try:
        with database.engine.begin() as connection:
            connection.execute(text("CREATE TABLE bootstrap_probe (value INTEGER NOT NULL)"))

        with database.session() as session:
            session.execute(text("INSERT INTO bootstrap_probe (value) VALUES (1)"))

        with pytest.raises(RuntimeError, match="rollback probe"):
            with database.session() as session:
                session.execute(text("INSERT INTO bootstrap_probe (value) VALUES (2)"))
                raise RuntimeError("rollback probe")

        with database.engine.connect() as connection:
            values = connection.execute(
                text("SELECT value FROM bootstrap_probe ORDER BY value")
            ).scalars()
            assert list(values) == [1]
    finally:
        database.dispose()
