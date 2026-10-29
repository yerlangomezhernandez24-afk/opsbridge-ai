"""Validated value objects used by ticket entities and events."""

import re
from dataclasses import dataclass
from uuid import UUID

from opsbridge.domain.tickets.enums import ActorRole
from opsbridge.domain.tickets.errors import InvalidIdentifierError

_TICKET_KEY_PATTERN = re.compile(r"^OPS-(?P<year>\d{4})-(?P<sequence>\d{6})$")
_ACTOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{1,127}$")


@dataclass(frozen=True, slots=True)
class TicketId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID) or self.value.version != 4:
            raise InvalidIdentifierError("ticket_id must be a UUID v4")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class TicketKey:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or _TICKET_KEY_PATTERN.fullmatch(self.value) is None:
            raise InvalidIdentifierError("ticket_key must use OPS-YYYY-NNNNNN")

    @property
    def year(self) -> int:
        match = _TICKET_KEY_PATTERN.fullmatch(self.value)
        if match is None:  # pragma: no cover - protected by construction
            raise InvalidIdentifierError("ticket_key must use OPS-YYYY-NNNNNN")
        return int(match.group("year"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ActorId:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or _ACTOR_ID_PATTERN.fullmatch(self.value) is None:
            raise InvalidIdentifierError("actor_id has an invalid format")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Actor:
    id: ActorId
    role: ActorRole

    def __post_init__(self) -> None:
        if not isinstance(self.id, ActorId):
            raise InvalidIdentifierError("actor.id must be an ActorId")
        if not isinstance(self.role, ActorRole):
            raise InvalidIdentifierError("actor.role must be an ActorRole")
