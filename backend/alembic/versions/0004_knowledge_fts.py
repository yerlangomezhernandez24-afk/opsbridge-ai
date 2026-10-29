"""Add synthetic knowledge documents and FTS5 retrieval.

Revision ID: 0004_knowledge_fts
Revises: 0003_ticket_api_idempotency
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_knowledge_fts"
down_revision: str | None = "0003_ticket_api_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("source_label", sa.String(120), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_documents_code", "knowledge_documents", ["code"], unique=True)
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chunk_id", sa.String(80), nullable=False),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_knowledge_chunk_order"),
    )
    op.create_index("ix_knowledge_chunks_chunk_id", "knowledge_chunks", ["chunk_id"], unique=True)
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_table(
        "knowledge_document_roles",
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(24), primary_key=True),
        sa.CheckConstraint(
            "role IN ('requester','technician','approver')", name="ck_knowledge_role"
        ),
    )
    op.execute(
        "CREATE VIRTUAL TABLE knowledge_fts USING fts5(heading, content, "
        "content='knowledge_chunks', content_rowid='id', tokenize='unicode61 remove_diacritics 2')"
    )
    op.execute(
        "CREATE TRIGGER knowledge_chunks_ai AFTER INSERT ON knowledge_chunks BEGIN "
        "INSERT INTO knowledge_fts(rowid, heading, content) "
        "VALUES (new.id, new.heading, new.content); END"
    )
    op.execute(
        "CREATE TRIGGER knowledge_chunks_ad AFTER DELETE ON knowledge_chunks BEGIN "
        "INSERT INTO knowledge_fts(knowledge_fts, rowid, heading, content) "
        "VALUES ('delete', old.id, old.heading, old.content); END"
    )
    op.execute(
        "CREATE TRIGGER knowledge_chunks_au AFTER UPDATE ON knowledge_chunks BEGIN "
        "INSERT INTO knowledge_fts(knowledge_fts, rowid, heading, content) "
        "VALUES ('delete', old.id, old.heading, old.content); "
        "INSERT INTO knowledge_fts(rowid, heading, content) "
        "VALUES (new.id, new.heading, new.content); END"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_au")
    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_ad")
    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_ai")
    op.execute("DROP TABLE IF EXISTS knowledge_fts")
    op.drop_table("knowledge_document_roles")
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_chunk_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_knowledge_documents_code", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
