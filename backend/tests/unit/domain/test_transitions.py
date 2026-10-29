"""Exhaustive ticket state-machine tests."""

from datetime import datetime, timedelta

import pytest

from opsbridge.domain.tickets import (
    Actor,
    ActorId,
    ActorRole,
    InvalidTimestampError,
    InvalidTransitionError,
    StaleTicketVersionError,
    TicketStatus,
    TransitionContext,
    TransitionPreconditionError,
    UnauthorizedDomainOperationError,
)
from tests.unit.domain.support import (
    APPROVER,
    AUTOMATION,
    BASE_TIME,
    OTHER_REQUESTER,
    REQUESTER,
    TECHNICIAN,
    build_ticket_at,
    next_time,
    valid_transition_input,
)

EXPECTED_TARGETS = {
    TicketStatus.NEW: {TicketStatus.TRIAGED, TicketStatus.CANCELLED},
    TicketStatus.TRIAGED: {TicketStatus.IN_PROGRESS, TicketStatus.CANCELLED},
    TicketStatus.IN_PROGRESS: {
        TicketStatus.WAITING_APPROVAL,
        TicketStatus.WAITING_REQUESTER,
        TicketStatus.RESOLVED,
        TicketStatus.CANCELLED,
    },
    TicketStatus.WAITING_APPROVAL: {TicketStatus.IN_PROGRESS, TicketStatus.CANCELLED},
    TicketStatus.WAITING_REQUESTER: {TicketStatus.IN_PROGRESS, TicketStatus.CANCELLED},
    TicketStatus.RESOLVED: {
        TicketStatus.IN_PROGRESS,
        TicketStatus.CLOSED,
        TicketStatus.CANCELLED,
    },
    TicketStatus.CLOSED: set(),
    TicketStatus.CANCELLED: set(),
}

ALLOWED_EDGES = [
    (source, target)
    for source, targets in EXPECTED_TARGETS.items()
    for target in sorted(targets, key=lambda item: item.value)
]
PROHIBITED_EDGES = [
    (source, target)
    for source, targets in EXPECTED_TARGETS.items()
    for target in TicketStatus
    if target is not source and target not in targets
]


@pytest.mark.parametrize("status", list(TicketStatus))
def test_allowed_target_contract_is_exact(status: TicketStatus) -> None:
    assert set(build_ticket_at(status).allowed_targets(status)) == EXPECTED_TARGETS[status]


@pytest.mark.parametrize(("source", "target"), ALLOWED_EDGES)
def test_every_allowed_transition_succeeds(source: TicketStatus, target: TicketStatus) -> None:
    ticket = build_ticket_at(source)
    actor, context = valid_transition_input(source, target)
    previous_version = ticket.version

    changed = ticket.transition(
        target,
        actor=actor,
        occurred_at=next_time(ticket),
        context=context,
        expected_version=previous_version,
    )

    assert changed is True
    assert ticket.status is target
    assert ticket.version == previous_version + 1


@pytest.mark.parametrize(("source", "target"), PROHIBITED_EDGES)
def test_every_prohibited_transition_is_rejected_without_mutation(
    source: TicketStatus, target: TicketStatus
) -> None:
    ticket = build_ticket_at(source)
    snapshot = (ticket.status, ticket.version, ticket.updated_at, ticket.history)

    with pytest.raises(InvalidTransitionError):
        ticket.transition(target, actor=TECHNICIAN, occurred_at=next_time(ticket))

    assert (ticket.status, ticket.version, ticket.updated_at, ticket.history) == snapshot


@pytest.mark.parametrize("status", list(TicketStatus))
def test_repeated_transition_is_idempotent(status: TicketStatus) -> None:
    ticket = build_ticket_at(status)
    snapshot = (ticket.version, ticket.updated_at, ticket.history)
    assert ticket.transition(status, actor=TECHNICIAN, occurred_at=next_time(ticket)) is False
    assert (ticket.version, ticket.updated_at, ticket.history) == snapshot


def test_status_has_no_public_assignment_path() -> None:
    ticket = build_ticket_at(TicketStatus.NEW)
    with pytest.raises(AttributeError):
        ticket.status = TicketStatus.CLOSED  # type: ignore[misc]
    assert ticket.status is TicketStatus.NEW


@pytest.mark.parametrize(
    ("source", "target", "actor", "context"),
    [
        (
            TicketStatus.NEW,
            TicketStatus.TRIAGED,
            AUTOMATION,
            TransitionContext(),
        ),
        (
            TicketStatus.TRIAGED,
            TicketStatus.IN_PROGRESS,
            TECHNICIAN,
            TransitionContext(),
        ),
        (
            TicketStatus.IN_PROGRESS,
            TicketStatus.WAITING_APPROVAL,
            TECHNICIAN,
            TransitionContext(),
        ),
        (
            TicketStatus.WAITING_APPROVAL,
            TicketStatus.IN_PROGRESS,
            APPROVER,
            TransitionContext(),
        ),
        (
            TicketStatus.IN_PROGRESS,
            TicketStatus.WAITING_REQUESTER,
            TECHNICIAN,
            TransitionContext(),
        ),
        (
            TicketStatus.WAITING_REQUESTER,
            TicketStatus.IN_PROGRESS,
            REQUESTER,
            TransitionContext(),
        ),
        (
            TicketStatus.IN_PROGRESS,
            TicketStatus.RESOLVED,
            TECHNICIAN,
            TransitionContext(),
        ),
        (
            TicketStatus.RESOLVED,
            TicketStatus.IN_PROGRESS,
            TECHNICIAN,
            TransitionContext(),
        ),
        (
            TicketStatus.RESOLVED,
            TicketStatus.CLOSED,
            REQUESTER,
            TransitionContext(),
        ),
        (
            TicketStatus.RESOLVED,
            TicketStatus.CLOSED,
            TECHNICIAN,
            TransitionContext(),
        ),
        (
            TicketStatus.IN_PROGRESS,
            TicketStatus.CANCELLED,
            TECHNICIAN,
            TransitionContext(),
        ),
    ],
)
def test_transition_preconditions_are_required(
    source: TicketStatus,
    target: TicketStatus,
    actor: Actor,
    context: TransitionContext,
) -> None:
    ticket = build_ticket_at(source)
    with pytest.raises(TransitionPreconditionError):
        ticket.transition(target, actor=actor, occurred_at=next_time(ticket), context=context)


def test_valid_automation_classification_can_triage() -> None:
    ticket = build_ticket_at(TicketStatus.NEW)
    ticket.transition(
        TicketStatus.TRIAGED,
        actor=AUTOMATION,
        occurred_at=next_time(ticket),
        context=TransitionContext(classification_validated=True),
    )
    assert ticket.status is TicketStatus.TRIAGED


def test_requester_can_cancel_only_own_ticket_before_work() -> None:
    triaged = build_ticket_at(TicketStatus.TRIAGED)
    triaged.transition(
        TicketStatus.CANCELLED,
        actor=REQUESTER,
        occurred_at=next_time(triaged),
    )
    assert triaged.status is TicketStatus.CANCELLED

    in_progress = build_ticket_at(TicketStatus.IN_PROGRESS)
    with pytest.raises(UnauthorizedDomainOperationError):
        in_progress.transition(
            TicketStatus.CANCELLED,
            actor=REQUESTER,
            occurred_at=next_time(in_progress),
        )


def test_other_requester_cannot_act_on_ticket() -> None:
    ticket = build_ticket_at(TicketStatus.WAITING_REQUESTER)
    with pytest.raises(UnauthorizedDomainOperationError):
        ticket.transition(
            TicketStatus.IN_PROGRESS,
            actor=OTHER_REQUESTER,
            occurred_at=next_time(ticket),
            context=TransitionContext(requester_response_received=True),
        )


def test_role_mismatch_is_rejected() -> None:
    ticket = build_ticket_at(TicketStatus.TRIAGED)
    with pytest.raises(UnauthorizedDomainOperationError):
        ticket.transition(
            TicketStatus.IN_PROGRESS,
            actor=REQUESTER,
            occurred_at=next_time(ticket),
            context=TransitionContext(assignee_id=TECHNICIAN.id),
        )


def test_technician_closure_policy_requires_documented_reason() -> None:
    ticket = build_ticket_at(TicketStatus.RESOLVED)
    ticket.transition(
        TicketStatus.CLOSED,
        actor=TECHNICIAN,
        occurred_at=next_time(ticket),
        context=TransitionContext(reason="Closure timeout policy elapsed"),
    )
    assert ticket.status is TicketStatus.CLOSED


def test_operation_rejects_stale_version_without_mutation() -> None:
    ticket = build_ticket_at(TicketStatus.NEW)
    snapshot = (ticket.status, ticket.version, ticket.history)
    with pytest.raises(StaleTicketVersionError):
        ticket.transition(
            TicketStatus.TRIAGED,
            actor=TECHNICIAN,
            occurred_at=next_time(ticket),
            expected_version=0,
        )
    assert (ticket.status, ticket.version, ticket.history) == snapshot


@pytest.mark.parametrize(
    "occurred_at",
    [BASE_TIME - timedelta(seconds=1), datetime(2026, 10, 28, 13, 0)],
)
def test_operation_rejects_invalid_time_without_mutation(occurred_at: datetime) -> None:
    ticket = build_ticket_at(TicketStatus.NEW)
    snapshot = (ticket.status, ticket.version, ticket.updated_at, ticket.history)
    with pytest.raises(InvalidTimestampError):
        ticket.transition(TicketStatus.TRIAGED, actor=TECHNICIAN, occurred_at=occurred_at)
    assert (ticket.status, ticket.version, ticket.updated_at, ticket.history) == snapshot


def test_invalid_actor_object_is_controlled() -> None:
    ticket = build_ticket_at(TicketStatus.NEW)
    with pytest.raises(UnauthorizedDomainOperationError):
        ticket.transition(
            TicketStatus.TRIAGED,
            actor=Actor(ActorId("guest-user"), ActorRole.REQUESTER),
            occurred_at=next_time(ticket),
        )
