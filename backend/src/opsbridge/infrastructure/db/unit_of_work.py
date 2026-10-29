"""Explicit SQLAlchemy transaction boundary for ticket operations."""

from types import TracebackType

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from opsbridge.application.ports.tickets import (
    IdempotencyRepository,
    TicketKeyAllocator,
    TicketRepository,
)
from opsbridge.infrastructure.db.database import Database
from opsbridge.infrastructure.db.error_translation import translate_commit_error
from opsbridge.infrastructure.db.idempotency_repository import SqlAlchemyIdempotencyRepository
from opsbridge.infrastructure.db.key_allocator import SqliteTicketKeyAllocator
from opsbridge.infrastructure.db.ticket_repository import SqlAlchemyTicketRepository


class SqlAlchemyUnitOfWork:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._session: Session | None = None
        self._committed = False
        self.tickets: TicketRepository
        self.keys: TicketKeyAllocator
        self.idempotency: IdempotencyRepository

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        if self._session is not None:
            raise RuntimeError("unit of work is already active")
        self._session = self._database.create_session()
        self.tickets = SqlAlchemyTicketRepository(self._session)
        self.keys = SqliteTicketKeyAllocator(self._session)
        self.idempotency = SqlAlchemyIdempotencyRepository(self._session)
        self._committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        session = self._require_session()
        try:
            if not self._committed:
                session.rollback()
        finally:
            session.close()
            self._session = None

    def commit(self) -> None:
        session = self._require_session()
        if self._committed:
            raise RuntimeError("unit of work has already committed")
        try:
            session.commit()
        except SQLAlchemyError as exc:
            session.rollback()
            raise translate_commit_error(exc) from exc
        self._committed = True

    def rollback(self) -> None:
        self._require_session().rollback()

    def _require_session(self) -> Session:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        return self._session
