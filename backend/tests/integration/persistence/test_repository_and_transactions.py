"""Repository round-trip, rehydration, and transaction integration tests."""

from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select, text

from opsbridge.domain.tickets import (
    TicketCategory,
    TicketId,
    TicketImpact,
    TicketKey,
    TicketStatus,
    TicketUrgency,
    TransitionContext,
)
from opsbridge.infrastructure.db import (
    Base,
    CorruptPersistenceDataError,
    Database,
    DuplicateTicketError,
    SqlAlchemyUnitOfWork,
    TicketEventRecord,
    TicketNotFoundError,
    TicketRecord,
)
from tests.integration.persistence.support import make_ticket, persist_new_ticket
from tests.unit.domain.support import BASE_TIME, TECHNICIAN


def test_create_and_recover_by_id_and_key(database: Database) -> None:
    original = persist_new_ticket(database)

    with SqlAlchemyUnitOfWork(database) as unit:
        by_id = unit.tickets.get_by_id(original.id)
        by_key = unit.tickets.get_by_key(original.key)

    assert by_id.id == by_key.id == original.id
    assert by_id.key == original.key
    assert by_id.title == original.title
    assert by_id.description == original.description
    assert by_id.category is original.category
    assert by_id.priority is original.priority
    assert by_id.status is TicketStatus.NEW
    assert by_id.created_at == by_id.updated_at == BASE_TIME
    assert by_id.version == 1
    assert by_id.history == original.history


def test_recover_after_engine_and_connections_are_closed(tmp_path: Path) -> None:
    path = tmp_path / "reopen.db"
    url = f"sqlite+pysqlite:///{path.as_posix()}"
    first = Database(url)
    Base.metadata.create_all(first.engine)
    original = persist_new_ticket(first)
    first.dispose()

    second = Database(url)
    try:
        with SqlAlchemyUnitOfWork(second) as unit:
            recovered = unit.tickets.get_by_id(original.id)
        assert recovered.history == original.history
        assert recovered.created_at.tzinfo is not None
    finally:
        second.dispose()


def test_missing_ticket_raises_typed_error(database: Database) -> None:
    missing_id = TicketId(UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"))
    with SqlAlchemyUnitOfWork(database) as unit:
        with pytest.raises(TicketNotFoundError):
            unit.tickets.get_by_id(missing_id)
        with pytest.raises(TicketNotFoundError):
            unit.tickets.get_by_key(TicketKey("OPS-2026-999999"))


def test_save_of_missing_ticket_raises_typed_error(database: Database) -> None:
    ticket = make_ticket(key_value="OPS-2026-000001")
    with SqlAlchemyUnitOfWork(database) as unit:
        with pytest.raises(TicketNotFoundError):
            unit.tickets.save(ticket, expected_version=1)


def test_update_category_priority_state_version_and_history(database: Database) -> None:
    original = persist_new_ticket(database)
    with SqlAlchemyUnitOfWork(database) as unit:
        ticket = unit.tickets.get_by_id(original.id)
        persisted_version = ticket.version
        ticket.change_category(
            TicketCategory.SOFTWARE_APPLICATION,
            actor=TECHNICIAN,
            occurred_at=BASE_TIME + timedelta(minutes=1),
        )
        ticket.reassess_priority(
            TicketImpact.MULTIPLE_USERS,
            TicketUrgency.HIGH,
            actor=TECHNICIAN,
            occurred_at=BASE_TIME + timedelta(minutes=2),
        )
        ticket.transition(
            TicketStatus.TRIAGED,
            actor=TECHNICIAN,
            occurred_at=BASE_TIME + timedelta(minutes=3),
        )
        unit.tickets.save(ticket, expected_version=persisted_version)
        unit.commit()

    with SqlAlchemyUnitOfWork(database) as unit:
        recovered = unit.tickets.get_by_id(original.id)
    assert recovered.category is TicketCategory.SOFTWARE_APPLICATION
    assert recovered.priority.value == "p2"
    assert recovered.status is TicketStatus.TRIAGED
    assert recovered.version == 4
    assert len(recovered.history) == 4
    assert recovered.updated_at == BASE_TIME + timedelta(minutes=3)


def test_assignment_resolution_and_closure_round_trip(database: Database) -> None:
    original = persist_new_ticket(database)
    with SqlAlchemyUnitOfWork(database) as unit:
        ticket = unit.tickets.get_by_id(original.id)
        ticket.transition(
            TicketStatus.TRIAGED,
            actor=TECHNICIAN,
            occurred_at=BASE_TIME + timedelta(minutes=1),
        )
        ticket.transition(
            TicketStatus.IN_PROGRESS,
            actor=TECHNICIAN,
            occurred_at=BASE_TIME + timedelta(minutes=2),
            context=TransitionContext(assignee_id=TECHNICIAN.id),
        )
        ticket.transition(
            TicketStatus.RESOLVED,
            actor=TECHNICIAN,
            occurred_at=BASE_TIME + timedelta(minutes=3),
            context=TransitionContext(resolution_summary="Configuration repaired"),
        )
        ticket.transition(
            TicketStatus.CLOSED,
            actor=TECHNICIAN,
            occurred_at=BASE_TIME + timedelta(minutes=4),
            context=TransitionContext(reason="Demo closure policy elapsed"),
        )
        expected_history = ticket.history
        unit.tickets.save(ticket, expected_version=1)
        unit.commit()

    with SqlAlchemyUnitOfWork(database) as unit:
        recovered = unit.tickets.get_by_id(original.id)
    assert recovered.status is TicketStatus.CLOSED
    assert recovered.assignee_id == TECHNICIAN.id
    assert recovered.resolution_summary == "Configuration repaired"
    assert recovered.history == expected_history
    assert recovered.version == 5


def test_idempotent_save_does_not_duplicate_events(database: Database) -> None:
    original = persist_new_ticket(database)
    with SqlAlchemyUnitOfWork(database) as unit:
        ticket = unit.tickets.get_by_id(original.id)
        assert (
            ticket.transition(
                TicketStatus.NEW,
                actor=TECHNICIAN,
                occurred_at=BASE_TIME + timedelta(minutes=1),
            )
            is False
        )
        unit.tickets.save(ticket, expected_version=1)
        unit.commit()

    with database.session() as session:
        count = session.scalar(select(func.count()).select_from(TicketEventRecord))
    assert count == 1


def test_exception_rolls_back_ticket_events_and_key_sequence(database: Database) -> None:
    with pytest.raises(RuntimeError, match="business failure"):
        with SqlAlchemyUnitOfWork(database) as unit:
            key = unit.keys.next_key(BASE_TIME)
            unit.tickets.add(make_ticket(key_value=str(key)))
            raise RuntimeError("business failure")

    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(TicketRecord)) == 0
        assert session.scalar(select(func.count()).select_from(TicketEventRecord)) == 0

    with SqlAlchemyUnitOfWork(database) as unit:
        assert str(unit.keys.next_key(BASE_TIME)) == "OPS-2026-000001"


def test_integrity_failure_rolls_back_complete_unit(database: Database) -> None:
    first = make_ticket(key_value="OPS-2026-000001", identifier=1)
    duplicate = make_ticket(key_value="OPS-2026-000002", identifier=1)
    with pytest.raises(DuplicateTicketError):
        with SqlAlchemyUnitOfWork(database) as unit:
            unit.tickets.add(first)
            unit.tickets.add(duplicate)
            unit.commit()

    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(TicketRecord)) == 0
        assert session.scalar(select(func.count()).select_from(TicketEventRecord)) == 0


def test_duplicate_public_key_is_distinguished(database: Database) -> None:
    persist_new_ticket(database, identifier=1)
    with pytest.raises(DuplicateTicketError):
        with SqlAlchemyUnitOfWork(database) as unit:
            unit.tickets.add(make_ticket(key_value="OPS-2026-000001", identifier=2))
            unit.commit()


def test_corrupt_event_payload_is_rejected_explicitly(database: Database) -> None:
    original = persist_new_ticket(database)
    with database.engine.begin() as connection:
        connection.execute(
            text("UPDATE ticket_events SET payload = :payload WHERE ticket_id = :ticket_id"),
            {"payload": '{"category":"unknown"}', "ticket_id": str(original.id)},
        )

    with SqlAlchemyUnitOfWork(database) as unit:
        with pytest.raises(CorruptPersistenceDataError):
            unit.tickets.get_by_id(original.id)


def test_valid_but_inconsistent_projection_is_rejected(database: Database) -> None:
    original = persist_new_ticket(database)
    with database.engine.begin() as connection:
        connection.execute(
            text("UPDATE tickets SET category = :category WHERE id = :ticket_id"),
            {"category": "software.application", "ticket_id": str(original.id)},
        )

    with SqlAlchemyUnitOfWork(database) as unit:
        with pytest.raises(CorruptPersistenceDataError):
            unit.tickets.get_by_id(original.id)
