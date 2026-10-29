"""Create ticket aggregate, event history, and key sequence tables.

Revision ID: 0001_ticket_persistence
Revises:
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_ticket_persistence"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticket_key_sequences",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("next_value", sa.Integer(), nullable=False),
        sa.CheckConstraint("year BETWEEN 1 AND 9999", name="ck_ticket_key_sequences_year"),
        sa.CheckConstraint(
            "next_value BETWEEN 2 AND 1000000",
            name="ck_ticket_key_sequences_next_value",
        ),
        sa.PrimaryKeyConstraint("year"),
    )
    op.create_table(
        "tickets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=15), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("impact", sa.String(length=32), nullable=False),
        sa.Column("urgency", sa.String(length=16), nullable=False),
        sa.Column("priority", sa.String(length=4), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("requester_id", sa.String(length=128), nullable=False),
        sa.Column("assignee_id", sa.String(length=128), nullable=True),
        sa.Column("resolution_summary", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("length(id) = 36", name="ck_tickets_id_length"),
        sa.CheckConstraint(
            "length(key) = 15 AND key GLOB "
            "'OPS-[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]'",
            name="ck_tickets_key_format",
        ),
        sa.CheckConstraint(
            "category IN ('network.vpn', 'software.application', "
            "'hardware.endpoint', 'access.application')",
            name="ck_tickets_category",
        ),
        sa.CheckConstraint(
            "impact IN ('single_user', 'multiple_users', 'organization')",
            name="ck_tickets_impact",
        ),
        sa.CheckConstraint("urgency IN ('low', 'medium', 'high')", name="ck_tickets_urgency"),
        sa.CheckConstraint("priority IN ('p1', 'p2', 'p3', 'p4')", name="ck_tickets_priority"),
        sa.CheckConstraint(
            "status IN ('new', 'triaged', 'in_progress', 'waiting_approval', "
            "'waiting_requester', 'resolved', 'closed', 'cancelled')",
            name="ck_tickets_status",
        ),
        sa.CheckConstraint("updated_at >= created_at", name="ck_tickets_timestamp_order"),
        sa.CheckConstraint("version >= 1", name="ck_tickets_version_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_table(
        "ticket_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("event_order", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "actor_role IN ('requester', 'technician', 'approver', 'automation')",
            name="ck_ticket_events_actor_role",
        ),
        sa.CheckConstraint("event_order >= 1", name="ck_ticket_events_order_positive"),
        sa.CheckConstraint("revision >= 1", name="ck_ticket_events_revision_positive"),
        sa.CheckConstraint(
            "event_type IN ('ticket_created', 'ticket_category_changed', "
            "'ticket_priority_reassessed', 'ticket_assigned', "
            "'ticket_status_changed', 'ticket_resolved', 'ticket_closed')",
            name="ck_ticket_events_type",
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id", "event_order", name="uq_ticket_events_order"),
    )
    op.create_index(
        "ix_ticket_events_ticket_revision",
        "ticket_events",
        ["ticket_id", "revision"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_events_ticket_revision", table_name="ticket_events")
    op.drop_table("ticket_events")
    op.drop_table("tickets")
    op.drop_table("ticket_key_sequences")
