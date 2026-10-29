"""Storage and cryptography ports for local authentication."""

from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from opsbridge.domain.identity import LocalUser, LoginId, UserId


class IdentityAlreadyExistsError(Exception):
    """A persistence adapter detected a duplicate local login."""


class StoredUser(Protocol):
    @property
    def user(self) -> LocalUser: ...

    @property
    def password_hash(self) -> str: ...


class StoredSession(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def user_id(self) -> UserId: ...

    @property
    def token_hash(self) -> str: ...

    @property
    def created_at(self) -> datetime: ...

    @property
    def last_seen_at(self) -> datetime: ...

    @property
    def absolute_expires_at(self) -> datetime: ...

    @property
    def idle_expires_at(self) -> datetime: ...

    @property
    def revoked_at(self) -> datetime | None: ...


class UserRepository(Protocol):
    def add(self, user: LocalUser, password_hash: str) -> None: ...

    def find_by_login(self, login_id: LoginId) -> StoredUser | None: ...

    def get_by_id(self, user_id: UserId) -> LocalUser | None: ...

    def update_password_hash(self, user_id: UserId, password_hash: str) -> None: ...


class SessionRepository(Protocol):
    def add(self, session: StoredSession) -> None: ...

    def find_by_token_hash(self, token_hash: str) -> StoredSession | None: ...

    def revoke(self, session_id: UUID, revoked_at: datetime) -> None: ...

    def touch(
        self, session_id: UUID, last_seen_at: datetime, idle_expires_at: datetime
    ) -> None: ...


class AuthUnitOfWork(Protocol):
    users: UserRepository
    sessions: SessionRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


class PasswordPort(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str | None, password: str) -> bool: ...

    def needs_rehash(self, password_hash: str) -> bool: ...


class TokenPort(Protocol):
    def issue(self) -> str: ...

    def verifier(self, token: str) -> str: ...

    def csrf_token(self, session_token: str) -> str: ...

    def csrf_matches(self, session_token: str, candidate: str) -> bool: ...
