"""Translate SQLAlchemy failures without leaking SQL, values, or local paths."""

from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from opsbridge.infrastructure.db.errors import (
    DatabaseLockedError,
    DuplicateTicketError,
    PersistenceError,
    PersistenceIntegrityError,
    TransactionFailureError,
)


def translate_operational_error(error: OperationalError) -> PersistenceError:
    message = str(error.orig).lower()
    if "locked" in message or "busy" in message:
        return DatabaseLockedError("database is temporarily locked")
    return TransactionFailureError("database operation failed")


def translate_commit_error(error: SQLAlchemyError) -> PersistenceError:
    if isinstance(error, IntegrityError):
        message = str(error.orig).lower()
        if "tickets.id" in message or "tickets.key" in message:
            return DuplicateTicketError("ticket identifier or key already exists")
        return PersistenceIntegrityError("database constraint rejected the transaction")
    if isinstance(error, OperationalError):
        return translate_operational_error(error)
    return TransactionFailureError("database transaction failed")
