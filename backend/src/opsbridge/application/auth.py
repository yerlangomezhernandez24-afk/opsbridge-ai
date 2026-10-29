"""Local authentication and opaque server-side session use cases."""

import hashlib
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from uuid import UUID

from opsbridge.application.authorization import AuthorizationPolicy, Permission
from opsbridge.application.errors import (
    AuthenticationRequiredError,
    DuplicateIdentityError,
    InvalidCredentialsError,
    PasswordPolicyError,
    SessionExpiredError,
    TooManyLoginAttemptsError,
)
from opsbridge.application.ports.auth import (
    AuthUnitOfWork,
    IdentityAlreadyExistsError,
    PasswordPort,
    TokenPort,
)
from opsbridge.domain.identity import IdentityValidationError, LocalUser, LoginId, UserId
from opsbridge.domain.tickets import ActorRole


@dataclass(frozen=True, slots=True)
class SessionState:
    user: LocalUser
    csrf_token: str
    expires_at: datetime
    permissions: tuple[Permission, ...]


@dataclass(frozen=True, slots=True)
class LoginResult:
    session_token: str
    state: SessionState


@dataclass(frozen=True, slots=True)
class NewSession:
    id: UUID
    user_id: UserId
    token_hash: str
    created_at: datetime
    last_seen_at: datetime
    absolute_expires_at: datetime
    idle_expires_at: datetime
    revoked_at: datetime | None = None


class LoginAttemptLimiter:
    """Small process-local limiter with injected time and no raw login retention."""

    def __init__(
        self,
        *,
        maximum_failures: int = 5,
        window: timedelta = timedelta(minutes=5),
        block_duration: timedelta = timedelta(minutes=5),
    ) -> None:
        self._maximum_failures = maximum_failures
        self._window = window
        self._block_duration = block_duration
        self._failures: dict[str, deque[datetime]] = {}
        self._blocked_until: dict[str, datetime] = {}
        self._lock = Lock()

    @staticmethod
    def key(login_id: str) -> str:
        normalized = login_id.strip().lower().encode("utf-8", errors="replace")
        return hashlib.sha256(normalized).hexdigest()

    def ensure_allowed(self, key: str, now: datetime) -> None:
        with self._lock:
            blocked_until = self._blocked_until.get(key)
            if blocked_until is not None and now < blocked_until:
                raise TooManyLoginAttemptsError
            if blocked_until is not None:
                self._blocked_until.pop(key, None)
                self._failures.pop(key, None)

    def failure(self, key: str, now: datetime) -> None:
        with self._lock:
            failures = self._failures.setdefault(key, deque())
            cutoff = now - self._window
            while failures and failures[0] < cutoff:
                failures.popleft()
            failures.append(now)
            if len(failures) >= self._maximum_failures:
                self._blocked_until[key] = now + self._block_duration

    def success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
            self._blocked_until.pop(key, None)


class AuthService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AuthUnitOfWork],
        passwords: PasswordPort,
        tokens: TokenPort,
        now: Callable[[], datetime],
        new_uuid: Callable[[], UUID],
        absolute_ttl: timedelta,
        idle_ttl: timedelta,
        limiter: LoginAttemptLimiter,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._passwords = passwords
        self._tokens = tokens
        self._now = now
        self._new_uuid = new_uuid
        self._absolute_ttl = absolute_ttl
        self._idle_ttl = idle_ttl
        self._limiter = limiter
        self._authorization = AuthorizationPolicy()

    def create_user(
        self,
        *,
        login_id: str,
        display_name: str,
        role: ActorRole,
        password: str,
    ) -> LocalUser:
        self._validate_new_password(password)
        now = self._now()
        user = LocalUser(
            id=UserId(self._new_uuid()),
            login_id=LoginId.parse(login_id),
            display_name=display_name,
            role=role,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        password_hash = self._passwords.hash(password)
        try:
            with self._unit_of_work_factory() as unit:
                unit.users.add(user, password_hash)
                unit.commit()
        except IdentityAlreadyExistsError as exc:
            raise DuplicateIdentityError from exc
        return user

    def login(
        self, *, login_id: str, password: str, existing_session_token: str | None
    ) -> LoginResult:
        now = self._now()
        limiter_key = self._limiter.key(login_id)
        self._limiter.ensure_allowed(limiter_key, now)
        account = None
        try:
            parsed_login = LoginId.parse(login_id)
        except IdentityValidationError:
            parsed_login = None
        with self._unit_of_work_factory() as unit:
            if parsed_login is not None:
                account = unit.users.find_by_login(parsed_login)
            password_hash = account.password_hash if account is not None else None
            verified = self._passwords.verify(password_hash, password)
            if account is None or not verified or not account.user.is_active:
                self._limiter.failure(limiter_key, now)
                raise InvalidCredentialsError
            if existing_session_token:
                previous = unit.sessions.find_by_token_hash(
                    self._tokens.verifier(existing_session_token)
                )
                if previous is not None and previous.revoked_at is None:
                    unit.sessions.revoke(previous.id, now)
            if self._passwords.needs_rehash(account.password_hash):
                unit.users.update_password_hash(account.user.id, self._passwords.hash(password))
            raw_token = self._tokens.issue()
            absolute_expires = now + self._absolute_ttl
            idle_expires = min(now + self._idle_ttl, absolute_expires)
            session = NewSession(
                id=self._new_uuid(),
                user_id=account.user.id,
                token_hash=self._tokens.verifier(raw_token),
                created_at=now,
                last_seen_at=now,
                absolute_expires_at=absolute_expires,
                idle_expires_at=idle_expires,
            )
            unit.sessions.add(session)
            unit.commit()
        self._limiter.success(limiter_key)
        return LoginResult(
            session_token=raw_token,
            state=self._state(account.user, raw_token, idle_expires),
        )

    def session(self, session_token: str) -> SessionState:
        now = self._now()
        with self._unit_of_work_factory() as unit:
            stored = unit.sessions.find_by_token_hash(self._tokens.verifier(session_token))
            if stored is None or stored.revoked_at is not None:
                raise AuthenticationRequiredError
            user = unit.users.get_by_id(stored.user_id)
            if user is None or not user.is_active:
                unit.sessions.revoke(stored.id, now)
                unit.commit()
                raise AuthenticationRequiredError
            if now >= stored.absolute_expires_at or now >= stored.idle_expires_at:
                unit.sessions.revoke(stored.id, now)
                unit.commit()
                raise SessionExpiredError
            idle_expires = min(now + self._idle_ttl, stored.absolute_expires_at)
            unit.sessions.touch(stored.id, now, idle_expires)
            unit.commit()
        return self._state(user, session_token, idle_expires)

    def logout(self, session_token: str) -> None:
        now = self._now()
        with self._unit_of_work_factory() as unit:
            stored = unit.sessions.find_by_token_hash(self._tokens.verifier(session_token))
            if stored is None or stored.revoked_at is not None:
                raise AuthenticationRequiredError
            user = unit.users.get_by_id(stored.user_id)
            if user is None or not user.is_active:
                raise AuthenticationRequiredError
            if now >= stored.absolute_expires_at or now >= stored.idle_expires_at:
                raise SessionExpiredError
            unit.sessions.revoke(stored.id, now)
            unit.commit()

    def csrf_matches(self, session_token: str, candidate: str) -> bool:
        return self._tokens.csrf_matches(session_token, candidate)

    def _state(self, user: LocalUser, session_token: str, expires_at: datetime) -> SessionState:
        permissions = tuple(
            sorted(self._authorization.permissions_for(user), key=lambda item: item.value)
        )
        return SessionState(
            user=user,
            csrf_token=self._tokens.csrf_token(session_token),
            expires_at=expires_at,
            permissions=permissions,
        )

    @staticmethod
    def _validate_new_password(password: str) -> None:
        if not isinstance(password, str) or not 12 <= len(password) <= 128:
            raise PasswordPolicyError
        if password.isspace():
            raise PasswordPolicyError
