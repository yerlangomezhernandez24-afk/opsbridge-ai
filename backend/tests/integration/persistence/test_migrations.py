"""Alembic migration tests against disposable SQLite files."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from opsbridge.infrastructure.db import Database

BACKEND_DIRECTORY = Path(__file__).resolve().parents[3]


def _config(database_path: Path) -> Config:
    config = Config(str(BACKEND_DIRECTORY / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIRECTORY / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path.as_posix()}")
    return config


def test_empty_database_upgrades_to_expected_schema_and_downgrades(tmp_path: Path) -> None:
    path = tmp_path / "migration.db"
    config = _config(path)
    command.upgrade(config, "head")

    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    try:
        inspector = inspect(database.engine)
        assert {
            "tickets",
            "ticket_events",
            "ticket_key_sequences",
            "users",
            "auth_sessions",
            "knowledge_documents",
            "knowledge_chunks",
            "knowledge_document_roles",
            "knowledge_fts",
            "action_proposals",
            "action_executions",
            "simulated_vpn_sessions",
            "tool_audit",
        }.issubset(inspector.get_table_names())
        assert {column["name"] for column in inspector.get_columns("tickets")} == {
            "id",
            "key",
            "title",
            "description",
            "category",
            "impact",
            "urgency",
            "priority",
            "status",
            "created_at",
            "updated_at",
            "requester_id",
            "assignee_id",
            "resolution_summary",
            "version",
        }
        foreign_keys = inspector.get_foreign_keys("ticket_events")
        assert foreign_keys[0]["referred_table"] == "tickets"
        indexes = inspector.get_indexes("ticket_events")
        assert any(item["name"] == "ix_ticket_events_ticket_revision" for item in indexes)
        session_foreign_keys = inspector.get_foreign_keys("auth_sessions")
        assert session_foreign_keys[0]["referred_table"] == "users"
    finally:
        database.dispose()

    command.downgrade(config, "0002_local_auth")
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    try:
        tables = inspect(database.engine).get_table_names()
        assert "idempotency_records" not in tables
        assert {"tickets", "users", "auth_sessions"}.issubset(tables)
    finally:
        database.dispose()
    command.upgrade(config, "head")

    command.check(config)
    command.downgrade(config, "base")
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    try:
        tables = inspect(database.engine).get_table_names()
        assert "tickets" not in tables
        assert "ticket_events" not in tables
        assert "ticket_key_sequences" not in tables
        assert "users" not in tables
        assert "auth_sessions" not in tables
    finally:
        database.dispose()


def test_migrated_schema_enforces_category_key_and_foreign_key_constraints(
    tmp_path: Path,
) -> None:
    path = tmp_path / "constraints.db"
    command.upgrade(_config(path), "head")
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    valid_values = {
        "id": "00000000-0000-4000-8000-000000000001",
        "key": "OPS-2026-000001",
        "title": "Valid title",
        "description": "A sufficiently descriptive persisted ticket.",
        "category": "network.vpn",
        "impact": "single_user",
        "urgency": "medium",
        "priority": "p3",
        "status": "new",
        "created_at": "2026-10-28 12:00:00",
        "updated_at": "2026-10-28 12:00:00",
        "requester_id": "requester-01",
        "version": 1,
    }
    insert_ticket = text(
        """
        INSERT INTO tickets (
            id, key, title, description, category, impact, urgency, priority,
            status, created_at, updated_at, requester_id, version
        ) VALUES (
            :id, :key, :title, :description, :category, :impact, :urgency, :priority,
            :status, :created_at, :updated_at, :requester_id, :version
        )
        """
    )
    try:
        with pytest.raises(IntegrityError):
            with database.engine.begin() as connection:
                connection.execute(insert_ticket, {**valid_values, "category": "unknown"})

        with database.engine.begin() as connection:
            connection.execute(insert_ticket, valid_values)
        with pytest.raises(IntegrityError):
            with database.engine.begin() as connection:
                connection.execute(
                    insert_ticket,
                    {
                        **valid_values,
                        "id": "00000000-0000-4000-8000-000000000002",
                    },
                )

        with pytest.raises(IntegrityError):
            with database.engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO ticket_events (
                            ticket_id, event_order, event_type, actor_id, actor_role,
                            occurred_at, revision, payload
                        ) VALUES (
                            :ticket_id, 1, 'ticket_created', 'requester-01', 'requester',
                            '2026-10-28 12:00:00', 1, '{}'
                        )
                        """
                    ),
                    {"ticket_id": "ffffffff-ffff-4fff-8fff-ffffffffffff"},
                )
    finally:
        database.dispose()


def test_auth_migration_upgrades_existing_ticket_schema_without_data_loss(
    tmp_path: Path,
) -> None:
    path = tmp_path / "incremental-auth.db"
    config = _config(path)
    command.upgrade(config, "0001_ticket_persistence")
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    try:
        with database.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO tickets (
                        id, key, title, description, category, impact, urgency, priority,
                        status, created_at, updated_at, requester_id, version
                    ) VALUES (
                        '00000000-0000-4000-8000-000000000001', 'OPS-2026-000001',
                        'Existing ticket', 'Existing ticket survives the authentication migration.',
                        'network.vpn', 'single_user', 'medium', 'p3', 'new',
                        '2026-10-28 12:00:00', '2026-10-28 12:00:00', 'requester-01', 1
                    )
                    """
                )
            )
    finally:
        database.dispose()

    command.upgrade(config, "head")
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    try:
        with database.engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM tickets")) == 1
        assert {"users", "auth_sessions"}.issubset(inspect(database.engine).get_table_names())
    finally:
        database.dispose()


def test_ticket_api_migration_is_incremental_and_has_scoped_uniqueness(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ticket-api-migration.db"
    config = _config(path)
    command.upgrade(config, "0002_local_auth")
    command.upgrade(config, "head")
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    try:
        inspector = inspect(database.engine)
        assert "idempotency_records" in inspector.get_table_names()
        unique_constraints = inspector.get_unique_constraints("idempotency_records")
        assert any(item["name"] == "uq_idempotency_scope" for item in unique_constraints)
        foreign_keys = inspector.get_foreign_keys("idempotency_records")
        assert {item["referred_table"] for item in foreign_keys} == {"users", "tickets"}
        assert {item["name"] for item in inspector.get_indexes("tickets")} >= {
            "ix_tickets_created_id",
            "ix_tickets_requester_created",
        }
    finally:
        database.dispose()
