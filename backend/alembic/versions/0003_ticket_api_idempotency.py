"""Add ticket API idempotency and list indexes.

Revision ID: 0003_ticket_api_idempotency
Revises: 0002_local_auth
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_ticket_api_idempotency"
down_revision: str | None = "0002_local_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_tickets_created_id", "tickets", ["created_at", "id"])
    op.create_index("ix_tickets_requester_created", "tickets", ["requester_id", "created_at", "id"])
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=36), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("ticket_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("length(key) = 36", name="ck_idempotency_key_length"),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_idempotency_hash_length"),
        sa.CheckConstraint("expires_at > created_at", name="ck_idempotency_expiry_order"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "operation", "key", name="uq_idempotency_scope"),
    )
    op.create_index("ix_idempotency_expires_at", "idempotency_records", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_expires_at", table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index("ix_tickets_requester_created", table_name="tickets")
    op.drop_index("ix_tickets_created_id", table_name="tickets")
