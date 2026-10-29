"""Immutable, minimal ticket events suitable for later persistence."""

from dataclasses import dataclass
from datetime import datetime
from typing import TypeAlias

from opsbridge.domain.tickets.enums import TicketCategory, TicketPriority, TicketStatus
from opsbridge.domain.tickets.values import Actor, ActorId, TicketId, TicketKey


@dataclass(frozen=True, slots=True)
class TicketCreated:
    ticket_id: TicketId
    ticket_key: TicketKey
    actor: Actor
    occurred_at: datetime
    revision: int
    category: TicketCategory
    priority: TicketPriority
    priority_policy_version: str
    status: TicketStatus


@dataclass(frozen=True, slots=True)
class TicketCategoryChanged:
    ticket_id: TicketId
    ticket_key: TicketKey
    actor: Actor
    occurred_at: datetime
    revision: int
    previous: TicketCategory
    current: TicketCategory


@dataclass(frozen=True, slots=True)
class TicketPriorityReassessed:
    ticket_id: TicketId
    ticket_key: TicketKey
    actor: Actor
    occurred_at: datetime
    revision: int
    previous: TicketPriority
    current: TicketPriority
    policy_version: str


@dataclass(frozen=True, slots=True)
class TicketAssigned:
    ticket_id: TicketId
    ticket_key: TicketKey
    actor: Actor
    occurred_at: datetime
    revision: int
    assignee_id: ActorId


@dataclass(frozen=True, slots=True)
class TicketStatusChanged:
    ticket_id: TicketId
    ticket_key: TicketKey
    actor: Actor
    occurred_at: datetime
    revision: int
    previous: TicketStatus
    current: TicketStatus


@dataclass(frozen=True, slots=True)
class TicketResolved:
    ticket_id: TicketId
    ticket_key: TicketKey
    actor: Actor
    occurred_at: datetime
    revision: int


@dataclass(frozen=True, slots=True)
class TicketClosed:
    ticket_id: TicketId
    ticket_key: TicketKey
    actor: Actor
    occurred_at: datetime
    revision: int


TicketEvent: TypeAlias = (
    TicketCreated
    | TicketCategoryChanged
    | TicketPriorityReassessed
    | TicketAssigned
    | TicketStatusChanged
    | TicketResolved
    | TicketClosed
)
