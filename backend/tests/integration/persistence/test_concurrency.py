"""Deterministic optimistic-concurrency, key allocation, and lock tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import func, select, text

from opsbridge.domain.tickets import TicketCategory, TicketStatus
from opsbridge.infrastructure.db import (
    Base,
    Database,
    DatabaseLockedError,
    PersistenceIntegrityError,
    SqlAlchemyUnitOfWork,
    TicketEventRecord,
    TicketRecord,
    TicketVersionConflictError,
)
from tests.integration.persistence.support import make_ticket, persist_new_ticket
from tests.unit.domain.support import BASE_TIME, TECHNICIAN


def test_two_updates_from_same_version_do_not_lose_first_write(database: Database) -> None:
    original = persist_new_ticket(database)
    with SqlAlchemyUnitOfWork(database) as unit:
        first_copy = unit.tickets.get_by_id(original.id)
    with SqlAlchemyUnitOfWork(database) as unit:
        second_copy = unit.tickets.get_by_id(original.id)

    first_copy.change_category(
        TicketCategory.SOFTWARE_APPLICATION,
        actor=TECHNICIAN,
        occurred_at=BASE_TIME + timedelta(minutes=1),
    )
    second_copy.transition(
        TicketStatus.TRIAGED,
        actor=TECHNICIAN,
        occurred_at=BASE_TIME + timedelta(minutes=2),
    )

    with SqlAlchemyUnitOfWork(database) as unit:
        unit.tickets.save(first_copy, expected_version=1)
        unit.commit()

    with pytest.raises(TicketVersionConflictError):
        with SqlAlchemyUnitOfWork(database) as unit:
            unit.tickets.save(second_copy, expected_version=1)
            unit.commit()

    with SqlAlchemyUnitOfWork(database) as unit:
        recovered = unit.tickets.get_by_id(original.id)
    assert recovered.category is TicketCategory.SOFTWARE_APPLICATION
    assert recovered.status is TicketStatus.NEW
    assert recovered.version == 2
    assert len(recovered.history) == 2


def test_concurrent_key_allocation_is_unique_and_transactional(database: Database) -> None:
    workers = 8
    barrier = Barrier(workers)

    def create(index: int) -> str:
        barrier.wait(timeout=10)
        with SqlAlchemyUnitOfWork(database) as unit:
            key = unit.keys.next_key(BASE_TIME)
            unit.tickets.add(make_ticket(key_value=str(key), identifier=index + 1))
            unit.commit()
        return str(key)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        keys = list(executor.map(create, range(workers)))

    assert len(set(keys)) == workers
    assert set(keys) == {f"OPS-2026-{value:06d}" for value in range(1, workers + 1)}
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(TicketRecord)) == workers


def test_sqlite_lock_is_not_reported_as_version_conflict(tmp_path: Path) -> None:
    path = tmp_path / "locked.db"
    database = Database(
        f"sqlite+pysqlite:///{path.as_posix()}",
        busy_timeout_ms=50,
    )
    Base.metadata.create_all(database.engine)
    holder = database.engine.connect()
    try:
        holder.execute(text("BEGIN IMMEDIATE"))
        with pytest.raises(DatabaseLockedError):
            with SqlAlchemyUnitOfWork(database) as unit:
                unit.keys.next_key(BASE_TIME)
                unit.commit()
    finally:
        holder.rollback()
        holder.close()
        database.dispose()


def test_failed_stale_update_persists_no_event(database: Database) -> None:
    original = persist_new_ticket(database)
    with SqlAlchemyUnitOfWork(database) as unit:
        stale = unit.tickets.get_by_id(original.id)

    with SqlAlchemyUnitOfWork(database) as unit:
        current = unit.tickets.get_by_id(original.id)
        current.change_category(
            TicketCategory.ACCESS_APPLICATION,
            actor=TECHNICIAN,
            occurred_at=BASE_TIME + timedelta(minutes=1),
        )
        unit.tickets.save(current, expected_version=1)
        unit.commit()

    stale.transition(
        TicketStatus.TRIAGED,
        actor=TECHNICIAN,
        occurred_at=BASE_TIME + timedelta(minutes=2),
    )
    with pytest.raises(TicketVersionConflictError):
        with SqlAlchemyUnitOfWork(database) as unit:
            unit.tickets.save(stale, expected_version=1)

    with database.session() as session:
        event_count = session.scalar(select(func.count()).select_from(TicketEventRecord))
    assert event_count == 2


def test_sqlite_foreign_keys_and_wal_are_enabled(database: Database) -> None:
    with database.engine.connect() as connection:
        foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
        journal_mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar_one()
    assert foreign_keys == 1
    assert journal_mode == "wal"


def test_key_sequence_is_namespaced_by_year(database: Database) -> None:
    with SqlAlchemyUnitOfWork(database) as unit:
        first_2026 = unit.keys.next_key(BASE_TIME)
        first_2027 = unit.keys.next_key(datetime(2027, 1, 1, tzinfo=UTC))
        unit.commit()
    assert str(first_2026) == "OPS-2026-000001"
    assert str(first_2027) == "OPS-2027-000001"


def test_exhausted_annual_key_space_is_explicit(database: Database) -> None:
    with database.engine.begin() as connection:
        connection.execute(
            text("INSERT INTO ticket_key_sequences (year, next_value) VALUES (2026, 1000000)")
        )
    with pytest.raises(PersistenceIntegrityError, match="exhausted"):
        with SqlAlchemyUnitOfWork(database) as unit:
            unit.keys.next_key(BASE_TIME)
