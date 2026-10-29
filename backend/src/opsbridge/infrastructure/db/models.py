"""SQLAlchemy records for the ticket aggregate and its local event history."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from opsbridge.domain.tickets import (
    ActorRole,
    TicketCategory,
    TicketImpact,
    TicketPriority,
    TicketStatus,
    TicketUrgency,
)
from opsbridge.infrastructure.db.base import Base
from opsbridge.infrastructure.db.types import UTCDateTime


def _sql_values(values: list[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


_STATUS_VALUES = _sql_values([item.value for item in TicketStatus])
_CATEGORY_VALUES = _sql_values([item.value for item in TicketCategory])
_PRIORITY_VALUES = _sql_values([item.value for item in TicketPriority])
_IMPACT_VALUES = _sql_values([item.value for item in TicketImpact])
_URGENCY_VALUES = _sql_values([item.value for item in TicketUrgency])
_ROLE_VALUES = _sql_values([item.value for item in ActorRole])
_EVENT_TYPES = _sql_values(
    [
        "ticket_created",
        "ticket_category_changed",
        "ticket_priority_reassessed",
        "ticket_assigned",
        "ticket_status_changed",
        "ticket_resolved",
        "ticket_closed",
    ]
)


class TicketRecord(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("length(id) = 36", name="ck_tickets_id_length"),
        CheckConstraint(
            "length(key) = 15 AND key GLOB "
            "'OPS-[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]'",
            name="ck_tickets_key_format",
        ),
        CheckConstraint(f"category IN ({_CATEGORY_VALUES})", name="ck_tickets_category"),
        CheckConstraint(f"priority IN ({_PRIORITY_VALUES})", name="ck_tickets_priority"),
        CheckConstraint(f"impact IN ({_IMPACT_VALUES})", name="ck_tickets_impact"),
        CheckConstraint(f"urgency IN ({_URGENCY_VALUES})", name="ck_tickets_urgency"),
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="ck_tickets_status"),
        CheckConstraint("version >= 1", name="ck_tickets_version_positive"),
        CheckConstraint("updated_at >= created_at", name="ck_tickets_timestamp_order"),
        Index("ix_tickets_created_id", "created_at", "id"),
        Index("ix_tickets_requester_created", "requester_id", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key: Mapped[str] = mapped_column(String(15), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    impact: Mapped[str] = mapped_column(String(32), nullable=False)
    urgency: Mapped[str] = mapped_column(String(16), nullable=False)
    priority: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    requester_id: Mapped[str] = mapped_column(String(128), nullable=False)
    assignee_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolution_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class TicketEventRecord(Base):
    __tablename__ = "ticket_events"
    __table_args__ = (
        UniqueConstraint("ticket_id", "event_order", name="uq_ticket_events_order"),
        CheckConstraint("event_order >= 1", name="ck_ticket_events_order_positive"),
        CheckConstraint("revision >= 1", name="ck_ticket_events_revision_positive"),
        CheckConstraint(f"event_type IN ({_EVENT_TYPES})", name="ck_ticket_events_type"),
        CheckConstraint(f"actor_role IN ({_ROLE_VALUES})", name="ck_ticket_events_actor_role"),
        Index("ix_ticket_events_ticket_revision", "ticket_id", "revision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tickets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_order: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class TicketKeySequenceRecord(Base):
    __tablename__ = "ticket_key_sequences"
    __table_args__ = (
        CheckConstraint("year BETWEEN 1 AND 9999", name="ck_ticket_key_sequences_year"),
        CheckConstraint(
            "next_value BETWEEN 2 AND 1000000",
            name="ck_ticket_key_sequences_next_value",
        ),
    )

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("user_id", "operation", "key", name="uq_idempotency_scope"),
        CheckConstraint("length(key) = 36", name="ck_idempotency_key_length"),
        CheckConstraint("length(request_hash) = 64", name="ck_idempotency_hash_length"),
        CheckConstraint("expires_at > created_at", name="ck_idempotency_expiry_order"),
        Index("ix_idempotency_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(36), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    ticket_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
