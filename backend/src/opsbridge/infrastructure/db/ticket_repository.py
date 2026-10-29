"""SQLAlchemy repository for complete ticket aggregates."""

import builtins
from typing import Any, cast

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from opsbridge.application.ports.tickets import (
    TicketCount,
    TicketCursor,
    TicketDailyCount,
    TicketListQuery,
    TicketPage,
    TicketSummary,
    TicketSummaryQuery,
)
from opsbridge.domain.tickets import Ticket, TicketId, TicketKey
from opsbridge.infrastructure.db.error_translation import (
    translate_commit_error,
    translate_operational_error,
)
from opsbridge.infrastructure.db.errors import (
    TicketNotFoundError,
    TicketVersionConflictError,
)
from opsbridge.infrastructure.db.models import TicketEventRecord, TicketRecord
from opsbridge.infrastructure.db.ticket_mapper import (
    event_to_record,
    record_to_ticket,
    ticket_to_record,
    ticket_values,
)


class SqlAlchemyTicketRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, ticket: Ticket) -> None:
        record = ticket_to_record(ticket)
        self._session.add(record)
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise translate_commit_error(exc) from exc
        self._session.add_all(
            event_to_record(event, order) for order, event in enumerate(ticket.history, start=1)
        )

    def get_by_id(self, ticket_id: TicketId) -> Ticket:
        ticket = self.find_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFoundError("ticket was not found")
        return ticket

    def find_by_id(self, ticket_id: TicketId) -> Ticket | None:
        record = self._session.get(TicketRecord, str(ticket_id))
        return None if record is None else self._hydrate(record)

    def get_by_key(self, key: TicketKey) -> Ticket:
        record = self._session.scalar(select(TicketRecord).where(TicketRecord.key == str(key)))
        if record is None:
            raise TicketNotFoundError("ticket was not found")
        return self._hydrate(record)

    def save(self, ticket: Ticket, *, expected_version: int) -> None:
        values = ticket_values(ticket)
        values.pop("id")
        try:
            result = cast(
                CursorResult[tuple[object, ...]],
                self._session.execute(
                    update(TicketRecord)
                    .where(
                        TicketRecord.id == str(ticket.id),
                        TicketRecord.version == expected_version,
                    )
                    .values(**values)
                ),
            )
        except OperationalError as exc:
            raise translate_operational_error(exc) from exc
        if result.rowcount != 1:
            exists = self._session.scalar(
                select(TicketRecord.id).where(TicketRecord.id == str(ticket.id))
            )
            if exists is None:
                raise TicketNotFoundError("ticket was not found")
            raise TicketVersionConflictError("ticket version is no longer current")

        self._session.add_all(
            event_to_record(event, order)
            for order, event in enumerate(ticket.history, start=1)
            if event.revision > expected_version
        )

    def list(self, query: TicketListQuery) -> TicketPage:
        statement = select(TicketRecord)
        clauses = []
        if query.requester_id is not None:
            clauses.append(TicketRecord.requester_id == query.requester_id)
        if query.statuses:
            clauses.append(TicketRecord.status.in_([item.value for item in query.statuses]))
        if query.priorities:
            clauses.append(TicketRecord.priority.in_([item.value for item in query.priorities]))
        if query.categories:
            clauses.append(TicketRecord.category.in_([item.value for item in query.categories]))
        if query.assignee_id is not None:
            clauses.append(TicketRecord.assignee_id == query.assignee_id)
        if query.text is not None:
            escaped = query.text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            clauses.append(
                or_(
                    TicketRecord.title.ilike(pattern, escape="\\"),
                    TicketRecord.description.ilike(pattern, escape="\\"),
                    TicketRecord.key.ilike(pattern, escape="\\"),
                )
            )
        if query.cursor is not None:
            clauses.append(
                or_(
                    TicketRecord.created_at < query.cursor.created_at,
                    and_(
                        TicketRecord.created_at == query.cursor.created_at,
                        TicketRecord.id < str(query.cursor.ticket_id),
                    ),
                )
            )
        if clauses:
            statement = statement.where(*clauses)
        try:
            records = self._session.scalars(
                statement.order_by(TicketRecord.created_at.desc(), TicketRecord.id.desc()).limit(
                    query.page_size + 1
                )
            ).all()
            has_more = len(records) > query.page_size
            selected = records[: query.page_size]
            items = tuple(self._hydrate(record) for record in selected)
        except OperationalError as exc:
            raise translate_operational_error(exc) from exc
        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = TicketCursor(last.created_at, last.id)
        return TicketPage(items=items, next_cursor=next_cursor)

    def summarize(self, query: TicketSummaryQuery) -> TicketSummary:
        clauses = self._summary_clauses(query)

        def grouped(column: Any) -> tuple[TicketCount, ...]:
            rows = self._session.execute(
                select(column, func.count()).where(*clauses).group_by(column).order_by(column)
            ).all()
            return tuple(TicketCount(name=str(name), value=int(value)) for name, value in rows)

        day = func.date(TicketRecord.created_at).label("day")
        try:
            total = int(
                self._session.scalar(select(func.count()).select_from(TicketRecord).where(*clauses))
                or 0
            )
            daily_rows = self._session.execute(
                select(day, func.count()).where(*clauses).group_by(day).order_by(day)
            ).all()
            return TicketSummary(
                total=total,
                by_status=grouped(TicketRecord.status),
                by_priority=grouped(TicketRecord.priority),
                by_category=grouped(TicketRecord.category),
                created_by_day=tuple(
                    TicketDailyCount(day=str(created_day), value=int(value))
                    for created_day, value in daily_rows
                ),
            )
        except OperationalError as exc:
            raise translate_operational_error(exc) from exc

    @staticmethod
    def _summary_clauses(query: TicketSummaryQuery) -> builtins.list[Any]:
        clauses: list[Any] = []
        if query.requester_id is not None:
            clauses.append(TicketRecord.requester_id == query.requester_id)
        if query.statuses:
            clauses.append(TicketRecord.status.in_([item.value for item in query.statuses]))
        if query.priorities:
            clauses.append(TicketRecord.priority.in_([item.value for item in query.priorities]))
        if query.categories:
            clauses.append(TicketRecord.category.in_([item.value for item in query.categories]))
        if query.assignee_id is not None:
            clauses.append(TicketRecord.assignee_id == query.assignee_id)
        if query.text is not None:
            escaped = query.text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            clauses.append(
                or_(
                    TicketRecord.title.ilike(pattern, escape="\\"),
                    TicketRecord.description.ilike(pattern, escape="\\"),
                    TicketRecord.key.ilike(pattern, escape="\\"),
                )
            )
        return clauses

    def _hydrate(self, record: TicketRecord) -> Ticket:
        events = self._session.scalars(
            select(TicketEventRecord)
            .where(TicketEventRecord.ticket_id == record.id)
            .order_by(TicketEventRecord.event_order)
        ).all()
        return record_to_ticket(record, events)
