"""Persistent, transaction-scoped idempotency records."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from opsbridge.application.ports.tickets import StoredIdempotency
from opsbridge.domain.tickets import TicketId
from opsbridge.infrastructure.db.error_translation import translate_commit_error
from opsbridge.infrastructure.db.models import IdempotencyRecord


class SqlAlchemyIdempotencyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def delete_expired(self, now: datetime) -> None:
        try:
            self._session.execute(
                delete(IdempotencyRecord).where(IdempotencyRecord.expires_at <= now)
            )
        except SQLAlchemyError as exc:
            raise translate_commit_error(exc) from exc

    def get(self, *, user_id: str, operation: str, key: str) -> StoredIdempotency | None:
        try:
            record = self._session.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.user_id == user_id,
                    IdempotencyRecord.operation == operation,
                    IdempotencyRecord.key == key,
                )
            )
        except SQLAlchemyError as exc:
            raise translate_commit_error(exc) from exc
        if record is None:
            return None
        return StoredIdempotency(
            request_hash=record.request_hash,
            ticket_id=TicketId(UUID(record.ticket_id)) if record.ticket_id else None,
            response_json=record.response_json,
            expires_at=record.expires_at,
        )

    def reserve(
        self,
        *,
        user_id: str,
        operation: str,
        key: str,
        request_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> bool:
        statement = (
            insert(IdempotencyRecord)
            .values(
                user_id=user_id,
                operation=operation,
                key=key,
                request_hash=request_hash,
                created_at=created_at,
                expires_at=expires_at,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "operation", "key"])
            .returning(IdempotencyRecord.id)
        )
        try:
            return self._session.scalar(statement) is not None
        except SQLAlchemyError as exc:
            raise translate_commit_error(exc) from exc

    def complete(
        self,
        *,
        user_id: str,
        operation: str,
        key: str,
        ticket_id: TicketId,
        response_json: dict[str, object],
    ) -> None:
        try:
            self._session.execute(
                update(IdempotencyRecord)
                .where(
                    IdempotencyRecord.user_id == user_id,
                    IdempotencyRecord.operation == operation,
                    IdempotencyRecord.key == key,
                )
                .values(ticket_id=str(ticket_id), response_json=response_json)
            )
        except SQLAlchemyError as exc:
            raise translate_commit_error(exc) from exc
