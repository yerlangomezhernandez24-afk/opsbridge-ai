"""Authentication persistence, transactions, and deterministic expiry tests."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from opsbridge.application.auth import AuthService, LoginAttemptLimiter
from opsbridge.application.errors import DuplicateIdentityError, SessionExpiredError
from opsbridge.domain.tickets import ActorRole
from opsbridge.infrastructure.db import (
    AuthSessionRecord,
    Base,
    CorruptPersistenceDataError,
    Database,
    UserRecord,
)
from opsbridge.infrastructure.db.auth_unit_of_work import SqlAlchemyAuthUnitOfWork
from opsbridge.infrastructure.security import Argon2PasswordService, OpaqueTokenService

PASSWORD = "integration-only password"  # noqa: S105


def _service(database: Database, now: Callable[[], datetime]) -> AuthService:
    return AuthService(
        unit_of_work_factory=lambda: SqlAlchemyAuthUnitOfWork(database),
        passwords=Argon2PasswordService(),
        tokens=OpaqueTokenService(),
        now=now,
        new_uuid=uuid4,
        absolute_ttl=timedelta(hours=8),
        idle_ttl=timedelta(minutes=30),
        limiter=LoginAttemptLimiter(),
    )


def _create(service: AuthService, login: str = "persistent-user") -> None:
    service.create_user(
        login_id=login,
        display_name="Persistence User",
        role=ActorRole.TECHNICIAN,
        password=PASSWORD,
    )


def test_session_survives_database_and_service_restart(tmp_path: Path) -> None:
    path = tmp_path / "restart.db"
    url = f"sqlite+pysqlite:///{path.as_posix()}"
    now = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
    first_database = Database(url)
    Base.metadata.create_all(first_database.engine)
    first_service = _service(first_database, lambda: now)
    _create(first_service)
    login = first_service.login(
        login_id="persistent-user",
        password=PASSWORD,
        existing_session_token=None,
    )
    first_database.dispose()

    second_database = Database(url)
    try:
        restored = _service(second_database, lambda: now + timedelta(minutes=1)).session(
            login.session_token
        )
        assert str(restored.user.login_id) == "persistent-user"
        assert restored.user.role is ActorRole.TECHNICIAN
    finally:
        second_database.dispose()


def test_idle_expiry_is_deterministic_and_revokes_session(database: Database) -> None:
    current = [datetime(2026, 10, 28, 12, 0, tzinfo=UTC)]
    service = _service(database, lambda: current[0])
    _create(service, "expiring-user")
    login = service.login(
        login_id="expiring-user",
        password=PASSWORD,
        existing_session_token=None,
    )
    current[0] += timedelta(minutes=31)

    with pytest.raises(SessionExpiredError):
        service.session(login.session_token)
    with database.create_session() as session:
        record = session.scalar(select(AuthSessionRecord))
        assert record is not None and record.revoked_at == current[0]


def test_duplicate_login_rolls_back_without_partial_identity(database: Database) -> None:
    service = _service(database, lambda: datetime(2026, 10, 28, 12, 0, tzinfo=UTC))
    _create(service, "unique-user")

    with pytest.raises(DuplicateIdentityError):
        _create(service, "unique-user")
    with database.create_session() as session:
        count = session.scalar(select(func.count()).select_from(UserRecord))
        assert count == 1


def test_repository_rejects_corrupt_non_v4_identity(database: Database) -> None:
    now = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
    with database.session() as session:
        session.add(
            UserRecord(
                id=str(UUID("00000000-0000-1000-8000-000000000001")),
                login_id="corrupt-user",
                display_name="Corrupt User",
                password_hash="not-used",  # noqa: S106
                role="requester",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
    service = _service(database, lambda: now)
    with pytest.raises(CorruptPersistenceDataError, match="local identity data is invalid"):
        service.login(
            login_id="corrupt-user",
            password="irrelevant password",  # noqa: S106
            existing_session_token=None,
        )
