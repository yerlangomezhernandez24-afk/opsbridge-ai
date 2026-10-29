"""Add local identities and opaque server-side sessions.

Revision ID: 0002_local_auth
Revises: 0001_ticket_persistence
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_local_auth"
down_revision: str | None = "0001_ticket_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("login_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("length(id) = 36", name="ck_users_id_length"),
        sa.CheckConstraint(
            "length(login_id) BETWEEN 3 AND 64 AND login_id = lower(login_id)",
            name="ck_users_login_id",
        ),
        sa.CheckConstraint(
            "role IN ('requester', 'technician', 'approver')",
            name="ck_users_role",
        ),
        sa.CheckConstraint("updated_at >= created_at", name="ck_users_timestamp_order"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("login_id"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("length(id) = 36", name="ck_auth_sessions_id_length"),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_auth_sessions_token_hash"),
        sa.CheckConstraint("last_seen_at >= created_at", name="ck_auth_sessions_last_seen_order"),
        sa.CheckConstraint(
            "idle_expires_at <= absolute_expires_at",
            name="ck_auth_sessions_expiry_order",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index(
        "ix_auth_sessions_expiry",
        "auth_sessions",
        ["idle_expires_at", "absolute_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_expiry", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("users")
