"""Composition helpers shared by HTTP and controlled administration commands."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from opsbridge.application.auth import AuthService, LoginAttemptLimiter
from opsbridge.infrastructure.config import Settings
from opsbridge.infrastructure.db.auth_unit_of_work import SqlAlchemyAuthUnitOfWork
from opsbridge.infrastructure.db.database import Database
from opsbridge.infrastructure.security import Argon2PasswordService, OpaqueTokenService


def create_auth_service(database: Database, settings: Settings) -> AuthService:
    return AuthService(
        unit_of_work_factory=lambda: SqlAlchemyAuthUnitOfWork(database),
        passwords=Argon2PasswordService(),
        tokens=OpaqueTokenService(),
        now=lambda: datetime.now(UTC),
        new_uuid=uuid4,
        absolute_ttl=timedelta(minutes=settings.session_absolute_minutes),
        idle_ttl=timedelta(minutes=settings.session_idle_minutes),
        limiter=LoginAttemptLimiter(),
    )
