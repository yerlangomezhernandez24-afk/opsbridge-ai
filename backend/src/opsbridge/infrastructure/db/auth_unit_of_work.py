"""Explicit transaction boundary for local authentication operations."""

from types import TracebackType

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from opsbridge.application.ports.auth import (
    IdentityAlreadyExistsError,
    SessionRepository,
    UserRepository,
)
from opsbridge.infrastructure.db.auth_repository import (
    SqlAlchemySessionRepository,
    SqlAlchemyUserRepository,
)
from opsbridge.infrastructure.db.database import Database
from opsbridge.infrastructure.db.errors import PersistenceIntegrityError, TransactionFailureError


class SqlAlchemyAuthUnitOfWork:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._session: Session | None = None
        self._committed = False
        self.users: UserRepository
        self.sessions: SessionRepository

    def __enter__(self) -> "SqlAlchemyAuthUnitOfWork":
        if self._session is not None:
            raise RuntimeError("unit of work is already active")
        self._session = self._database.create_session()
        self.users = SqlAlchemyUserRepository(self._session)
        self.sessions = SqlAlchemySessionRepository(self._session)
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
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            if "users.login_id" in str(exc.orig):
                raise IdentityAlreadyExistsError from exc
            raise PersistenceIntegrityError from exc
        except SQLAlchemyError as exc:
            session.rollback()
            raise TransactionFailureError from exc
        self._committed = True

    def _require_session(self) -> Session:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        return self._session
