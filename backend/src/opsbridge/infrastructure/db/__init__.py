"""SQLAlchemy bootstrap and transaction policy."""

from opsbridge.infrastructure.db.base import Base
from opsbridge.infrastructure.db.database import Database
from opsbridge.infrastructure.db.errors import (
    CorruptPersistenceDataError,
    DatabaseLockedError,
    DuplicateTicketError,
    PersistenceError,
    PersistenceIntegrityError,
    TicketNotFoundError,
    TicketVersionConflictError,
    TransactionFailureError,
)
from opsbridge.infrastructure.db.identity_models import AuthSessionRecord, UserRecord
from opsbridge.infrastructure.db.key_allocator import SqliteTicketKeyAllocator
from opsbridge.infrastructure.db.models import (
    TicketEventRecord,
    TicketKeySequenceRecord,
    TicketRecord,
)
from opsbridge.infrastructure.db.ticket_repository import SqlAlchemyTicketRepository
from opsbridge.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

__all__ = [
    "AuthSessionRecord",
    "Base",
    "CorruptPersistenceDataError",
    "Database",
    "DatabaseLockedError",
    "DuplicateTicketError",
    "PersistenceError",
    "PersistenceIntegrityError",
    "SqlAlchemyTicketRepository",
    "SqlAlchemyUnitOfWork",
    "SqliteTicketKeyAllocator",
    "TicketEventRecord",
    "TicketKeySequenceRecord",
    "TicketNotFoundError",
    "TicketRecord",
    "TicketVersionConflictError",
    "TransactionFailureError",
    "UserRecord",
]
