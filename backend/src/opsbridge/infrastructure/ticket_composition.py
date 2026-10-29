"""Composition helper for ticket application use cases."""

from datetime import UTC, datetime
from uuid import uuid4

from opsbridge.application.tickets import TicketService
from opsbridge.infrastructure.db.database import Database
from opsbridge.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


def create_ticket_service(database: Database) -> TicketService:
    return TicketService(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(database),
        now=lambda: datetime.now(UTC),
        new_uuid=uuid4,
    )
