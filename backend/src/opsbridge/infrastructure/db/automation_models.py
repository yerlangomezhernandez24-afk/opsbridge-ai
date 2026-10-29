"""Persistence models for governed proposals and synthetic tool execution."""

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from opsbridge.infrastructure.db.base import Base
from opsbridge.infrastructure.db.types import UTCDateTime


class ActionProposalRecord(Base):
    __tablename__ = "action_proposals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_approval','approved','rejected','executed')",
            name="ck_action_proposals_status",
        ),
        CheckConstraint("length(arguments_hash) = 64", name="ck_action_arguments_hash"),
        CheckConstraint("source_mode IN ('rules','llm_local')", name="ck_action_source_mode"),
        CheckConstraint("expires_at > created_at", name="ck_action_expiry_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    ticket_version: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    arguments: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    arguments_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    proposer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    decision_actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ActionExecutionRecord(Base):
    __tablename__ = "action_executions"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_action_execution_proposal"),
        CheckConstraint("status IN ('succeeded','failed')", name="ck_action_execution_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("action_proposals.id", ondelete="RESTRICT"), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    result: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class SimulatedVpnSessionRecord(Base):
    __tablename__ = "simulated_vpn_sessions"
    __table_args__ = (
        CheckConstraint(
            "identity_code GLOB 'DEMO-VPN-[0-9][0-9][0-9]'",
            name="ck_simulated_vpn_identity",
        ),
        CheckConstraint("state IN ('locked','active')", name="ck_simulated_vpn_state"),
        CheckConstraint("reset_count >= 0", name="ck_simulated_vpn_reset_count"),
    )

    identity_code: Mapped[str] = mapped_column(String(12), primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    reset_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class ToolAuditRecord(Base):
    __tablename__ = "tool_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proposal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("action_proposals.id", ondelete="RESTRICT"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    operation: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
