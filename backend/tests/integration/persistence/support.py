"""Deterministic ticket persistence helpers."""

from datetime import datetime
from uuid import UUID

from opsbridge.domain.tickets import (
    Ticket,
    TicketCategory,
    TicketId,
    TicketImpact,
    TicketKey,
    TicketUrgency,
)
from opsbridge.infrastructure.db import Database, SqlAlchemyUnitOfWork
from tests.unit.domain.support import BASE_TIME, REQUESTER


def make_ticket(*, key_value: str, identifier: int = 1, created_at: datetime = BASE_TIME) -> Ticket:
    return Ticket.create(
        ticket_id=TicketId(UUID(f"00000000-0000-4000-8000-{identifier:012d}")),
        key=TicketKey(key_value),
        title="Persisted VPN incident",
        description="The synthetic requester cannot establish the corporate VPN connection.",
        category=TicketCategory.NETWORK_VPN,
        impact=TicketImpact.SINGLE_USER,
        urgency=TicketUrgency.MEDIUM,
        requester=REQUESTER,
        created_at=created_at,
    )


def persist_new_ticket(database: Database, *, identifier: int = 1) -> Ticket:
    with SqlAlchemyUnitOfWork(database) as unit:
        key = unit.keys.next_key(BASE_TIME)
        ticket = make_ticket(key_value=str(key), identifier=identifier)
        unit.tickets.add(ticket)
        unit.commit()
    return ticket
