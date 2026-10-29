"""Application-layer persistence contracts."""

from opsbridge.application.ports.auth import (
    AuthUnitOfWork,
    IdentityAlreadyExistsError,
    PasswordPort,
    SessionRepository,
    StoredSession,
    StoredUser,
    TokenPort,
    UserRepository,
)
from opsbridge.application.ports.tickets import (
    TicketKeyAllocator,
    TicketRepository,
    TicketUnitOfWork,
)

__all__ = [
    "AuthUnitOfWork",
    "IdentityAlreadyExistsError",
    "PasswordPort",
    "SessionRepository",
    "StoredSession",
    "StoredUser",
    "TicketKeyAllocator",
    "TicketRepository",
    "TicketUnitOfWork",
    "TokenPort",
    "UserRepository",
]
