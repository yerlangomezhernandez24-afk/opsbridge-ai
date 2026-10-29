"""Ports required to persist and query ticket aggregates transactionally."""

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from opsbridge.domain.tickets import (
    Ticket,
    TicketCategory,
    TicketId,
    TicketKey,
    TicketPriority,
    TicketStatus,
)


@dataclass(frozen=True, slots=True)
class TicketCursor:
    created_at: datetime
    ticket_id: TicketId


@dataclass(frozen=True, slots=True)
class TicketListQuery:
    requester_id: str | None
    statuses: tuple[TicketStatus, ...]
    priorities: tuple[TicketPriority, ...]
    categories: tuple[TicketCategory, ...]
    assignee_id: str | None
    text: str | None
    page_size: int
    cursor: TicketCursor | None


@dataclass(frozen=True, slots=True)
class TicketPage:
    items: tuple[Ticket, ...]
    next_cursor: TicketCursor | None


@dataclass(frozen=True, slots=True)
class TicketSummaryQuery:
    requester_id: str | None
    statuses: tuple[TicketStatus, ...]
    priorities: tuple[TicketPriority, ...]
    categories: tuple[TicketCategory, ...]
    assignee_id: str | None
    text: str | None


@dataclass(frozen=True, slots=True)
class TicketCount:
    name: str
    value: int


@dataclass(frozen=True, slots=True)
class TicketDailyCount:
    day: str
    value: int


@dataclass(frozen=True, slots=True)
class TicketSummary:
    total: int
    by_status: tuple[TicketCount, ...]
    by_priority: tuple[TicketCount, ...]
    by_category: tuple[TicketCount, ...]
    created_by_day: tuple[TicketDailyCount, ...]


@dataclass(frozen=True, slots=True)
class StoredIdempotency:
    request_hash: str
    ticket_id: TicketId | None
    response_json: dict[str, object] | None
    expires_at: datetime


class IdempotencyRepository(Protocol):
    def delete_expired(self, now: datetime) -> None: ...

    def get(self, *, user_id: str, operation: str, key: str) -> StoredIdempotency | None: ...

    def reserve(
        self,
        *,
        user_id: str,
        operation: str,
        key: str,
        request_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> bool: ...

    def complete(
        self,
        *,
        user_id: str,
        operation: str,
        key: str,
        ticket_id: TicketId,
        response_json: dict[str, object],
    ) -> None: ...


class TicketRepository(Protocol):
    def add(self, ticket: Ticket) -> None: ...

    def get_by_id(self, ticket_id: TicketId) -> Ticket: ...

    def find_by_id(self, ticket_id: TicketId) -> Ticket | None: ...

    def get_by_key(self, key: TicketKey) -> Ticket: ...

    def save(self, ticket: Ticket, *, expected_version: int) -> None: ...

    def list(self, query: TicketListQuery) -> TicketPage: ...

    def summarize(self, query: TicketSummaryQuery) -> TicketSummary: ...


class TicketKeyAllocator(Protocol):
    def next_key(self, created_at: datetime) -> TicketKey: ...


class TicketUnitOfWork(Protocol):
    tickets: TicketRepository
    keys: TicketKeyAllocator
    idempotency: IdempotencyRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
