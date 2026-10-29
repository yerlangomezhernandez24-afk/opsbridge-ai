"""Deterministic builders that reach states only through public domain operations."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from opsbridge.domain.tickets import (
    Actor,
    ActorId,
    ActorRole,
    Ticket,
    TicketCategory,
    TicketId,
    TicketImpact,
    TicketKey,
    TicketStatus,
    TicketUrgency,
    TransitionContext,
)

BASE_TIME = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
REQUESTER = Actor(ActorId("requester-01"), ActorRole.REQUESTER)
OTHER_REQUESTER = Actor(ActorId("requester-02"), ActorRole.REQUESTER)
TECHNICIAN = Actor(ActorId("technician-01"), ActorRole.TECHNICIAN)
APPROVER = Actor(ActorId("approver-01"), ActorRole.APPROVER)
AUTOMATION = Actor(ActorId("rules-engine"), ActorRole.AUTOMATION)


def new_ticket() -> Ticket:
    return Ticket.create(
        ticket_id=TicketId(UUID("12345678-1234-4234-8234-123456789abc")),
        key=TicketKey("OPS-2026-000001"),
        title="VPN unavailable",
        description="The requester cannot establish the corporate VPN connection.",
        category=TicketCategory.NETWORK_VPN,
        impact=TicketImpact.SINGLE_USER,
        urgency=TicketUrgency.MEDIUM,
        requester=REQUESTER,
        created_at=BASE_TIME,
    )


def build_ticket_at(status: TicketStatus) -> Ticket:
    ticket = new_ticket()
    minute = 1

    def move(target: TicketStatus, actor: Actor, context: TransitionContext) -> None:
        nonlocal minute
        ticket.transition(
            target,
            actor=actor,
            occurred_at=BASE_TIME + timedelta(minutes=minute),
            context=context,
        )
        minute += 1

    if status is TicketStatus.NEW:
        return ticket
    if status is TicketStatus.CANCELLED:
        move(TicketStatus.CANCELLED, REQUESTER, TransitionContext())
        return ticket

    move(TicketStatus.TRIAGED, TECHNICIAN, TransitionContext())
    if status is TicketStatus.TRIAGED:
        return ticket

    move(
        TicketStatus.IN_PROGRESS,
        TECHNICIAN,
        TransitionContext(assignee_id=TECHNICIAN.id),
    )
    if status is TicketStatus.IN_PROGRESS:
        return ticket
    if status is TicketStatus.WAITING_APPROVAL:
        move(
            TicketStatus.WAITING_APPROVAL,
            TECHNICIAN,
            TransitionContext(approval_reference="APR-001"),
        )
        return ticket
    if status is TicketStatus.WAITING_REQUESTER:
        move(
            TicketStatus.WAITING_REQUESTER,
            TECHNICIAN,
            TransitionContext(reason="Need diagnostic details"),
        )
        return ticket

    move(
        TicketStatus.RESOLVED,
        TECHNICIAN,
        TransitionContext(resolution_summary="VPN profile was repaired and verified."),
    )
    if status is TicketStatus.RESOLVED:
        return ticket
    if status is TicketStatus.CLOSED:
        move(
            TicketStatus.CLOSED,
            REQUESTER,
            TransitionContext(requester_confirmed=True),
        )
        return ticket
    raise AssertionError(f"unsupported state fixture: {status}")


def valid_transition_input(
    source: TicketStatus, target: TicketStatus
) -> tuple[Actor, TransitionContext]:
    if target is TicketStatus.CANCELLED:
        return TECHNICIAN, TransitionContext(reason="Documented cancellation")
    if (source, target) == (TicketStatus.NEW, TicketStatus.TRIAGED):
        return TECHNICIAN, TransitionContext()
    if (source, target) == (TicketStatus.TRIAGED, TicketStatus.IN_PROGRESS):
        return TECHNICIAN, TransitionContext(assignee_id=TECHNICIAN.id)
    if (source, target) == (TicketStatus.IN_PROGRESS, TicketStatus.WAITING_APPROVAL):
        return TECHNICIAN, TransitionContext(approval_reference="APR-001")
    if (source, target) == (TicketStatus.WAITING_APPROVAL, TicketStatus.IN_PROGRESS):
        return APPROVER, TransitionContext(approval_resolved=True)
    if (source, target) == (TicketStatus.IN_PROGRESS, TicketStatus.WAITING_REQUESTER):
        return TECHNICIAN, TransitionContext(reason="Need requester information")
    if (source, target) == (TicketStatus.WAITING_REQUESTER, TicketStatus.IN_PROGRESS):
        return REQUESTER, TransitionContext(requester_response_received=True)
    if (source, target) == (TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED):
        return TECHNICIAN, TransitionContext(resolution_summary="Verified resolution")
    if (source, target) == (TicketStatus.RESOLVED, TicketStatus.IN_PROGRESS):
        return TECHNICIAN, TransitionContext(reason="Issue reproduced")
    if (source, target) == (TicketStatus.RESOLVED, TicketStatus.CLOSED):
        return REQUESTER, TransitionContext(requester_confirmed=True)
    raise AssertionError(f"no valid input for {source} -> {target}")


def next_time(ticket: Ticket) -> datetime:
    return ticket.updated_at + timedelta(minutes=1)
