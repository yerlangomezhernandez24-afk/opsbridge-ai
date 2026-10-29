"""Persistence failures that remain independent from HTTP concerns."""


class PersistenceError(Exception):
    """Base class for storage adapter failures."""


class TicketNotFoundError(PersistenceError):
    """The requested ticket does not exist."""


class DuplicateTicketError(PersistenceError):
    """A ticket identifier or public key already exists."""


class TicketVersionConflictError(PersistenceError):
    """A conditional ticket update used an obsolete persisted version."""


class PersistenceIntegrityError(PersistenceError):
    """Stored data or a pending write violates a database constraint."""


class TransactionFailureError(PersistenceError):
    """A database transaction could not be completed."""


class DatabaseLockedError(PersistenceError):
    """SQLite is temporarily locked or busy."""


class CorruptPersistenceDataError(PersistenceError):
    """Persisted data cannot be safely reconstructed as a domain object."""
