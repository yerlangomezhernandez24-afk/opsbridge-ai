"""SQLAlchemy repositories for local identities and server-side sessions."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from opsbridge.application.ports.auth import StoredSession, StoredUser
from opsbridge.domain.identity import IdentityValidationError, LocalUser, LoginId, UserId
from opsbridge.domain.tickets import ActorRole
from opsbridge.infrastructure.db.errors import CorruptPersistenceDataError
from opsbridge.infrastructure.db.identity_models import AuthSessionRecord, UserRecord


@dataclass(frozen=True, slots=True)
class StoredUserData:
    user: LocalUser
    password_hash: str


@dataclass(frozen=True, slots=True)
class StoredSessionData:
    id: UUID
    user_id: UserId
    token_hash: str
    created_at: datetime
    last_seen_at: datetime
    absolute_expires_at: datetime
    idle_expires_at: datetime
    revoked_at: datetime | None


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user: LocalUser, password_hash: str) -> None:
        self._session.add(
            UserRecord(
                id=str(user.id),
                login_id=str(user.login_id),
                display_name=user.display_name,
                password_hash=password_hash,
                role=user.role.value,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        )

    def find_by_login(self, login_id: LoginId) -> StoredUser | None:
        record = self._session.scalar(
            select(UserRecord).where(UserRecord.login_id == str(login_id))
        )
        return None if record is None else self._stored(record)

    def get_by_id(self, user_id: UserId) -> LocalUser | None:
        record = self._session.get(UserRecord, str(user_id))
        return None if record is None else self._stored(record).user

    def update_password_hash(self, user_id: UserId, password_hash: str) -> None:
        self._session.execute(
            update(UserRecord)
            .where(UserRecord.id == str(user_id))
            .values(password_hash=password_hash)
        )

    @staticmethod
    def _stored(record: UserRecord) -> StoredUserData:
        try:
            user = LocalUser(
                id=UserId(UUID(record.id)),
                login_id=LoginId.parse(record.login_id),
                display_name=record.display_name,
                role=ActorRole(record.role),
                is_active=record.is_active,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
        except (ValueError, IdentityValidationError) as exc:
            raise CorruptPersistenceDataError("local identity data is invalid") from exc
        return StoredUserData(user=user, password_hash=record.password_hash)


class SqlAlchemySessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, session: StoredSession) -> None:
        self._session.add(
            AuthSessionRecord(
                id=str(session.id),
                user_id=str(session.user_id),
                token_hash=session.token_hash,
                created_at=session.created_at,
                last_seen_at=session.last_seen_at,
                absolute_expires_at=session.absolute_expires_at,
                idle_expires_at=session.idle_expires_at,
                revoked_at=session.revoked_at,
            )
        )

    def find_by_token_hash(self, token_hash: str) -> StoredSessionData | None:
        record = self._session.scalar(
            select(AuthSessionRecord).where(AuthSessionRecord.token_hash == token_hash)
        )
        return None if record is None else self._stored(record)

    def revoke(self, session_id: UUID, revoked_at: datetime) -> None:
        self._session.execute(
            update(AuthSessionRecord)
            .where(AuthSessionRecord.id == str(session_id))
            .values(revoked_at=revoked_at)
        )

    def touch(self, session_id: UUID, last_seen_at: datetime, idle_expires_at: datetime) -> None:
        self._session.execute(
            update(AuthSessionRecord)
            .where(AuthSessionRecord.id == str(session_id))
            .values(last_seen_at=last_seen_at, idle_expires_at=idle_expires_at)
        )

    @staticmethod
    def _stored(record: AuthSessionRecord) -> StoredSessionData:
        try:
            session_id = UUID(record.id)
            user_id = UserId(UUID(record.user_id))
        except (ValueError, IdentityValidationError) as exc:
            raise CorruptPersistenceDataError("authentication session data is invalid") from exc
        return StoredSessionData(
            id=session_id,
            user_id=user_id,
            token_hash=record.token_hash,
            created_at=record.created_at,
            last_seen_at=record.last_seen_at,
            absolute_expires_at=record.absolute_expires_at,
            idle_expires_at=record.idle_expires_at,
            revoked_at=record.revoked_at,
        )
