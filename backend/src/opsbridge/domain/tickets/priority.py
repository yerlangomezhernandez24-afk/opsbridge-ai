"""Deterministic priority policy; no AI or external service is involved."""

from types import MappingProxyType
from typing import Final

from opsbridge.domain.tickets.enums import TicketImpact, TicketPriority, TicketUrgency
from opsbridge.domain.tickets.errors import InvalidPriorityInputError

PRIORITY_POLICY_VERSION: Final = "impact-urgency-v1"

_PRIORITY_MATRIX = MappingProxyType(
    {
        (TicketImpact.SINGLE_USER, TicketUrgency.LOW): TicketPriority.P4,
        (TicketImpact.SINGLE_USER, TicketUrgency.MEDIUM): TicketPriority.P3,
        (TicketImpact.SINGLE_USER, TicketUrgency.HIGH): TicketPriority.P3,
        (TicketImpact.MULTIPLE_USERS, TicketUrgency.LOW): TicketPriority.P4,
        (TicketImpact.MULTIPLE_USERS, TicketUrgency.MEDIUM): TicketPriority.P3,
        (TicketImpact.MULTIPLE_USERS, TicketUrgency.HIGH): TicketPriority.P2,
        (TicketImpact.ORGANIZATION, TicketUrgency.LOW): TicketPriority.P3,
        (TicketImpact.ORGANIZATION, TicketUrgency.MEDIUM): TicketPriority.P2,
        (TicketImpact.ORGANIZATION, TicketUrgency.HIGH): TicketPriority.P1,
    }
)


def calculate_priority(impact: TicketImpact, urgency: TicketUrgency) -> TicketPriority:
    """Return the approved priority for an explicit impact/urgency pair."""

    if not isinstance(impact, TicketImpact) or not isinstance(urgency, TicketUrgency):
        raise InvalidPriorityInputError("impact and urgency must use approved values")
    return _PRIORITY_MATRIX[(impact, urgency)]
