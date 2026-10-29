"""Atomic SQLite-backed allocation of human-readable ticket keys."""

from datetime import datetime, timedelta

from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from opsbridge.domain.tickets import TicketKey
from opsbridge.infrastructure.db.error_translation import translate_operational_error
from opsbridge.infrastructure.db.errors import PersistenceIntegrityError
from opsbridge.infrastructure.db.models import TicketKeySequenceRecord


class SqliteTicketKeyAllocator:
    def __init__(self, session: Session) -> None:
        self._session = session

    def next_key(self, created_at: datetime) -> TicketKey:
        if created_at.tzinfo is None or created_at.utcoffset() != timedelta(0):
            raise PersistenceIntegrityError("ticket key allocation requires a UTC timestamp")
        statement = (
            insert(TicketKeySequenceRecord)
            .values(year=created_at.year, next_value=2)
            .on_conflict_do_update(
                index_elements=[TicketKeySequenceRecord.year],
                set_={"next_value": TicketKeySequenceRecord.next_value + 1},
            )
            .returning(TicketKeySequenceRecord.next_value - 1)
        )
        try:
            sequence = self._session.execute(statement).scalar_one()
        except IntegrityError as exc:
            raise PersistenceIntegrityError("annual ticket key space is exhausted") from exc
        except OperationalError as exc:
            raise translate_operational_error(exc) from exc
        if not 1 <= sequence <= 999999:
            raise PersistenceIntegrityError("annual ticket key space is exhausted")
        return TicketKey(f"OPS-{created_at.year:04d}-{sequence:06d}")
