"""Concrete SQLAlchemy engine, health check, and transaction boundary."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


class Database:
    """Own the engine and provide short commit-or-rollback sessions."""

    def __init__(self, url: str, *, busy_timeout_ms: int = 5000) -> None:
        self._prepare_sqlite_directory(url)
        parsed = make_url(url)
        is_sqlite = parsed.get_backend_name() == "sqlite"
        connect_args = (
            {"check_same_thread": False, "timeout": busy_timeout_ms / 1000} if is_sqlite else {}
        )
        self.engine: Engine = create_engine(
            url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        if is_sqlite:
            is_file_database = parsed.database not in {None, "", ":memory:"}
            event.listen(
                self.engine,
                "connect",
                _sqlite_connection_setup(busy_timeout_ms, is_file_database),
            )
        self._session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

    @staticmethod
    def _prepare_sqlite_directory(url: str) -> None:
        parsed = make_url(url)
        if parsed.get_backend_name() != "sqlite":
            return
        database = parsed.database
        if database and database != ":memory:":
            Path(database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

    def ping(self) -> None:
        """Raise on failure without returning database or path details."""

        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Commit on success and roll back before re-raising on failure."""

        database_session = self._session_factory()
        try:
            yield database_session
            database_session.commit()
        except Exception:
            database_session.rollback()
            raise
        finally:
            database_session.close()

    def create_session(self) -> Session:
        """Open a session whose commit/rollback lifecycle belongs to the caller."""

        return self._session_factory()

    def dispose(self) -> None:
        self.engine.dispose()


def _sqlite_connection_setup(busy_timeout_ms: int, enable_wal: bool) -> Callable[[Any, Any], None]:
    def configure(dbapi_connection: Any, connection_record: Any) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
            if enable_wal:
                cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()

    return configure
