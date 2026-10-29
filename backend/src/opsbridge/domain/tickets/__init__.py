"""Public ticket-domain API."""

from opsbridge.domain.tickets.enums import (
    ActorRole,
    TicketCategory,
    TicketImpact,
    TicketPriority,
    TicketStatus,
    TicketUrgency,
)
from opsbridge.domain.tickets.errors import (
    InvalidCategoryError,
    InvalidIdentifierError,
    InvalidPriorityInputError,
    InvalidTimestampError,
    InvalidTransitionError,
    StaleTicketVersionError,
    TicketDomainError,
    TicketValidationError,
    TransitionPreconditionError,
    UnauthorizedDomainOperationError,
)
from opsbridge.domain.tickets.events import (
    TicketAssigned,
    TicketCategoryChanged,
    TicketClosed,
    TicketCreated,
    TicketEvent,
    TicketPriorityReassessed,
    TicketResolved,
    TicketStatusChanged,
)
from opsbridge.domain.tickets.priority import PRIORITY_POLICY_VERSION, calculate_priority
from opsbridge.domain.tickets.ticket import Ticket, TransitionContext
from opsbridge.domain.tickets.values import Actor, ActorId, TicketId, TicketKey

__all__ = [
    "PRIORITY_POLICY_VERSION",
    "Actor",
    "ActorId",
    "ActorRole",
    "InvalidCategoryError",
    "InvalidIdentifierError",
    "InvalidPriorityInputError",
    "InvalidTimestampError",
    "InvalidTransitionError",
    "StaleTicketVersionError",
    "Ticket",
    "TicketAssigned",
    "TicketCategory",
    "TicketCategoryChanged",
    "TicketClosed",
    "TicketCreated",
    "TicketDomainError",
    "TicketEvent",
    "TicketId",
    "TicketImpact",
    "TicketKey",
    "TicketPriority",
    "TicketPriorityReassessed",
    "TicketResolved",
    "TicketStatus",
    "TicketStatusChanged",
    "TicketUrgency",
    "TicketValidationError",
    "TransitionContext",
    "TransitionPreconditionError",
    "UnauthorizedDomainOperationError",
    "calculate_priority",
]
