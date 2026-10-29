"""Role-scoped lexical retrieval with verifiable citations and abstention."""

import hashlib
import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from opsbridge.application.errors import MalformedRequestError, ResourceNotFoundError
from opsbridge.domain.tickets import ActorRole
from opsbridge.infrastructure.db.database import Database
from opsbridge.infrastructure.db.error_translation import (
    translate_commit_error,
    translate_operational_error,
)
from opsbridge.infrastructure.db.knowledge_models import (
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
    KnowledgeDocumentRoleModel,
)

_TERM_PATTERN = re.compile(r"[^\W_]{2,}", re.UNICODE)


class CorpusChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^KB-[A-Z]+-\d{3}-C\d{2}$", max_length=80)
    heading: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=20, max_length=2000)


class CorpusDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(pattern=r"^KB-[A-Z]+-\d{3}$", max_length=64)
    title: str = Field(min_length=5, max_length=200)
    version: str = Field(min_length=1, max_length=32)
    source_label: str = Field(min_length=5, max_length=120)
    roles: list[ActorRole] = Field(min_length=1, max_length=3)
    chunks: list[CorpusChunk] = Field(min_length=1, max_length=50)


class CorpusManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = Field(ge=1, le=1)
    documents: list[CorpusDocument] = Field(min_length=1, max_length=100)


@dataclass(frozen=True)
class Citation:
    document_code: str
    document_title: str
    document_version: str
    chunk_id: str
    heading: str
    content: str
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    mode: str
    query: str
    abstained: bool
    citations: tuple[Citation, ...]


class KnowledgeService:
    """Persist bundled synthetic documents and retrieve authorized chunks."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def ingest(self, manifest: CorpusManifest) -> tuple[int, int]:
        inserted = 0
        unchanged = 0
        with _write_session(self._database) as session:
            for document in manifest.documents:
                canonical = json.dumps(
                    document.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
                )
                checksum = hashlib.sha256(canonical.encode()).hexdigest()
                existing = session.scalar(
                    select(KnowledgeDocumentModel).where(
                        KnowledgeDocumentModel.code == document.code
                    )
                )
                if existing is not None and existing.checksum == checksum:
                    unchanged += 1
                    continue
                if existing is not None:
                    session.execute(
                        delete(KnowledgeDocumentRoleModel).where(
                            KnowledgeDocumentRoleModel.document_id == existing.id
                        )
                    )
                    session.execute(
                        delete(KnowledgeChunkModel).where(
                            KnowledgeChunkModel.document_id == existing.id
                        )
                    )
                    existing.title = document.title
                    existing.version = document.version
                    existing.source_label = document.source_label
                    existing.checksum = checksum
                    document_id = existing.id
                else:
                    document_id = str(uuid4())
                    session.add(
                        KnowledgeDocumentModel(
                            id=document_id,
                            code=document.code,
                            title=document.title,
                            version=document.version,
                            source_label=document.source_label,
                            checksum=checksum,
                            created_at=datetime.now(UTC),
                        )
                    )
                session.flush()
                session.add_all(
                    KnowledgeDocumentRoleModel(document_id=document_id, role=role.value)
                    for role in set(document.roles)
                )
                session.add_all(
                    KnowledgeChunkModel(
                        chunk_id=chunk.id,
                        document_id=document_id,
                        ordinal=ordinal,
                        heading=chunk.heading,
                        content=chunk.content,
                    )
                    for ordinal, chunk in enumerate(document.chunks, start=1)
                )
                inserted += 1
        return inserted, unchanged

    def search(self, *, query: str, role: ActorRole, limit: int = 5) -> RetrievalResult:
        normalized = query.strip()
        if not normalized or len(normalized) > 200 or not 1 <= limit <= 10:
            raise MalformedRequestError
        terms = list(dict.fromkeys(term.casefold() for term in _TERM_PATTERN.findall(normalized)))
        if not terms:
            raise MalformedRequestError
        fts_query = " AND ".join(f'"{term}"' for term in terms[:12])
        statement = text(
            "SELECT d.code, d.title, d.version, c.chunk_id, c.heading, c.content, "
            "bm25(knowledge_fts, 2.0, 1.0) AS rank "
            "FROM knowledge_fts "
            "JOIN knowledge_chunks c ON c.id = knowledge_fts.rowid "
            "JOIN knowledge_documents d ON d.id = c.document_id "
            "JOIN knowledge_document_roles r ON r.document_id = d.id "
            "WHERE knowledge_fts MATCH :query AND r.role = :role "
            "ORDER BY rank, d.code, c.ordinal LIMIT :limit"
        )
        with _read_session(self._database) as session:
            rows = session.execute(
                statement, {"query": fts_query, "role": role.value, "limit": limit}
            ).mappings()
            citations = tuple(
                Citation(
                    document_code=str(row["code"]),
                    document_title=str(row["title"]),
                    document_version=str(row["version"]),
                    chunk_id=str(row["chunk_id"]),
                    heading=str(row["heading"]),
                    content=str(row["content"]),
                    # FTS5 bm25 ranks better matches with lower (normally negative)
                    # values. Expose a non-negative relevance magnitude to callers.
                    score=round(max(0.0, -float(row["rank"])), 6),
                )
                for row in rows
            )
        return RetrievalResult(
            mode="rag_lexical", query=normalized, abstained=not citations, citations=citations
        )

    def chunk(self, *, document_code: str, chunk_id: str, role: ActorRole) -> Citation:
        statement = text(
            "SELECT d.code, d.title, d.version, c.chunk_id, c.heading, c.content "
            "FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id "
            "JOIN knowledge_document_roles r ON r.document_id=d.id "
            "WHERE d.code=:code AND c.chunk_id=:chunk_id AND r.role=:role"
        )
        with _read_session(self._database) as session:
            row: Any = (
                session.execute(
                    statement,
                    {"code": document_code, "chunk_id": chunk_id, "role": role.value},
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise ResourceNotFoundError
        return Citation(
            document_code=str(row["code"]),
            document_title=str(row["title"]),
            document_version=str(row["version"]),
            chunk_id=str(row["chunk_id"]),
            heading=str(row["heading"]),
            content=str(row["content"]),
            score=0.0,
        )


@contextmanager
def _write_session(database: Database) -> Iterator[Session]:
    try:
        with database.session() as session:
            yield session
    except OperationalError as exc:
        raise translate_operational_error(exc) from exc
    except SQLAlchemyError as exc:
        raise translate_commit_error(exc) from exc


@contextmanager
def _read_session(database: Database) -> Iterator[Session]:
    try:
        with database.create_session() as session:
            yield session
    except OperationalError as exc:
        raise translate_operational_error(exc) from exc
    except SQLAlchemyError as exc:
        raise translate_commit_error(exc) from exc
