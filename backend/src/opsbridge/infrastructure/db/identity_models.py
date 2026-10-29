"""SQLAlchemy records for local identities and opaque sessions."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from opsbridge.infrastructure.db.base import Base
from opsbridge.infrastructure.db.types import UTCDateTime


class UserRecord(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(id) = 36", name="ck_users_id_length"),
        CheckConstraint(
            "length(login_id) BETWEEN 3 AND 64 AND login_id = lower(login_id)",
            name="ck_users_login_id",
        ),
        CheckConstraint(
            "role IN ('requester', 'technician', 'approver')",
            name="ck_users_role",
        ),
        CheckConstraint("updated_at >= created_at", name="ck_users_timestamp_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    login_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class AuthSessionRecord(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint("length(id) = 36", name="ck_auth_sessions_id_length"),
        CheckConstraint("length(token_hash) = 64", name="ck_auth_sessions_token_hash"),
        CheckConstraint(
            "last_seen_at >= created_at",
            name="ck_auth_sessions_last_seen_order",
        ),
        CheckConstraint(
            "idle_expires_at <= absolute_expires_at",
            name="ck_auth_sessions_expiry_order",
        ),
        Index("ix_auth_sessions_user_id", "user_id"),
        Index("ix_auth_sessions_expiry", "idle_expires_at", "absolute_expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
