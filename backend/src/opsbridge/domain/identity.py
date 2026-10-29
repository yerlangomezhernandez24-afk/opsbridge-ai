"""Framework-independent local identity values."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from opsbridge.domain.tickets import ActorId, ActorRole

_LOGIN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
_HUMAN_ROLES = frozenset({ActorRole.REQUESTER, ActorRole.TECHNICIAN, ActorRole.APPROVER})


class IdentityValidationError(ValueError):
    """A local identity violates a stable domain invariant."""


@dataclass(frozen=True, slots=True)
class UserId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID) or self.value.version != 4:
            raise IdentityValidationError("user_id must be a UUID v4")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class LoginId:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or _LOGIN_PATTERN.fullmatch(self.value) is None:
            raise IdentityValidationError("login_id has an invalid format")

    @classmethod
    def parse(cls, value: str) -> "LoginId":
        if not isinstance(value, str):
            raise IdentityValidationError("login_id must be text")
        return cls(value.strip().lower())

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class LocalUser:
    id: UserId
    login_id: LoginId
    display_name: str
    role: ActorRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        display_name = self.display_name.strip()
        if not 1 <= len(display_name) <= 100:
            raise IdentityValidationError("display_name length must be between 1 and 100")
        if self.role not in _HUMAN_ROLES:
            raise IdentityValidationError("local users require an approved human role")
        _require_utc(self.created_at)
        _require_utc(self.updated_at)
        if self.updated_at < self.created_at:
            raise IdentityValidationError("updated_at cannot precede created_at")
        object.__setattr__(self, "display_name", display_name)

    @property
    def actor_id(self) -> ActorId:
        return ActorId(str(self.id))


def _require_utc(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise IdentityValidationError("identity timestamps must be timezone-aware UTC")
