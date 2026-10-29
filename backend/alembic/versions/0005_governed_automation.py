"""Add governed action proposals, approvals, execution, and VPN simulator.

Revision ID: 0005_governed_automation
Revises: 0004_knowledge_fts
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_governed_automation"
down_revision: str | None = "0004_knowledge_fts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "action_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ticket_id", sa.String(36), nullable=False),
        sa.Column("ticket_version", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("source_mode", sa.String(16), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("arguments_hash", sa.String(64), nullable=False),
        sa.Column("proposer_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decision_actor_id", sa.String(36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["proposer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decision_actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('pending_approval','approved','rejected','executed')",
            name="ck_action_proposals_status",
        ),
        sa.CheckConstraint("length(arguments_hash) = 64", name="ck_action_arguments_hash"),
        sa.CheckConstraint("source_mode IN ('rules','llm_local')", name="ck_action_source_mode"),
        sa.CheckConstraint("expires_at > created_at", name="ck_action_expiry_order"),
    )
    op.create_index("ix_action_proposals_ticket_id", "action_proposals", ["ticket_id"])
    op.create_index("ix_action_proposals_proposer_id", "action_proposals", ["proposer_id"])
    op.create_index("ix_action_proposals_expires_at", "action_proposals", ["expires_at"])
    op.create_table(
        "action_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("proposal_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["action_proposals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("proposal_id", name="uq_action_execution_proposal"),
        sa.CheckConstraint("status IN ('succeeded','failed')", name="ck_action_execution_status"),
    )
    op.create_table(
        "simulated_vpn_sessions",
        sa.Column("identity_code", sa.String(12), primary_key=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("reset_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "identity_code GLOB 'DEMO-VPN-[0-9][0-9][0-9]'",
            name="ck_simulated_vpn_identity",
        ),
        sa.CheckConstraint("state IN ('locked','active')", name="ck_simulated_vpn_state"),
        sa.CheckConstraint("reset_count >= 0", name="ck_simulated_vpn_reset_count"),
    )
    op.create_table(
        "tool_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("proposal_id", sa.String(36), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("operation", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["action_proposals.id"], ondelete="RESTRICT"),
    )


def downgrade() -> None:
    op.drop_table("tool_audit")
    op.drop_table("simulated_vpn_sessions")
    op.drop_table("action_executions")
    op.drop_index("ix_action_proposals_expires_at", table_name="action_proposals")
    op.drop_index("ix_action_proposals_proposer_id", table_name="action_proposals")
    op.drop_index("ix_action_proposals_ticket_id", table_name="action_proposals")
    op.drop_table("action_proposals")
