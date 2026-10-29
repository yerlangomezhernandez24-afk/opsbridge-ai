"""Audit history and controlled ticket update tests."""

from dataclasses import FrozenInstanceError, fields

import pytest

from opsbridge.domain.tickets import (
    InvalidCategoryError,
    StaleTicketVersionError,
    TicketAssigned,
    TicketCategory,
    TicketCategoryChanged,
    TicketClosed,
    TicketImpact,
    TicketPriority,
    TicketPriorityReassessed,
    TicketResolved,
    TicketStatus,
    TicketStatusChanged,
    TicketUrgency,
    TransitionContext,
    TransitionPreconditionError,
    UnauthorizedDomainOperationError,
)
from tests.unit.domain.support import (
    REQUESTER,
    TECHNICIAN,
    build_ticket_at,
    new_ticket,
    next_time,
)


def test_category_change_is_controlled_versioned_and_audited() -> None:
    ticket = new_ticket()
    changed = ticket.change_category(
        TicketCategory.SOFTWARE_APPLICATION,
        actor=TECHNICIAN,
        occurred_at=next_time(ticket),
        expected_version=1,
    )
    assert changed is True
    assert ticket.category is TicketCategory.SOFTWARE_APPLICATION
    assert ticket.version == 2
    assert isinstance(ticket.history[-1], TicketCategoryChanged)
    assert ticket.history[-1].revision == 2


def test_same_category_is_idempotent() -> None:
    ticket = new_ticket()
    snapshot = (ticket.version, ticket.updated_at, ticket.history)
    assert (
        ticket.change_category(
            TicketCategory.NETWORK_VPN,
            actor=TECHNICIAN,
            occurred_at=next_time(ticket),
        )
        is False
    )
    assert (ticket.version, ticket.updated_at, ticket.history) == snapshot


def test_category_change_rejects_unapproved_value_and_role() -> None:
    ticket = new_ticket()
    with pytest.raises(InvalidCategoryError):
        ticket.change_category(
            "network.other",  # type: ignore[arg-type]
            actor=TECHNICIAN,
            occurred_at=next_time(ticket),
        )
    with pytest.raises(UnauthorizedDomainOperationError):
        ticket.change_category(
            TicketCategory.SOFTWARE_APPLICATION,
            actor=REQUESTER,
            occurred_at=next_time(ticket),
        )


def test_priority_reassessment_updates_inputs_and_derived_value() -> None:
    ticket = new_ticket()
    changed = ticket.reassess_priority(
        TicketImpact.ORGANIZATION,
        TicketUrgency.HIGH,
        actor=TECHNICIAN,
        occurred_at=next_time(ticket),
    )
    assert changed is True
    assert ticket.impact is TicketImpact.ORGANIZATION
    assert ticket.urgency is TicketUrgency.HIGH
    assert ticket.priority is TicketPriority.P1
    assert ticket.version == 2
    event = ticket.history[-1]
    assert isinstance(event, TicketPriorityReassessed)
    assert event.previous is TicketPriority.P3
    assert event.current is TicketPriority.P1
    assert event.policy_version == "impact-urgency-v1"


def test_priority_reassessment_records_changed_inputs_even_if_band_is_same() -> None:
    ticket = new_ticket()
    ticket.reassess_priority(
        TicketImpact.SINGLE_USER,
        TicketUrgency.HIGH,
        actor=TECHNICIAN,
        occurred_at=next_time(ticket),
    )
    assert ticket.priority is TicketPriority.P3
    assert ticket.urgency is TicketUrgency.HIGH
    assert isinstance(ticket.history[-1], TicketPriorityReassessed)


def test_same_priority_inputs_are_idempotent() -> None:
    ticket = new_ticket()
    snapshot = (ticket.version, ticket.updated_at, ticket.history)
    assert (
        ticket.reassess_priority(
            TicketImpact.SINGLE_USER,
            TicketUrgency.MEDIUM,
            actor=TECHNICIAN,
            occurred_at=next_time(ticket),
        )
        is False
    )
    assert (ticket.version, ticket.updated_at, ticket.history) == snapshot


def test_terminal_ticket_cannot_be_recategorized_or_reprioritized() -> None:
    ticket = build_ticket_at(TicketStatus.CLOSED)
    with pytest.raises(TransitionPreconditionError):
        ticket.change_category(
            TicketCategory.HARDWARE_ENDPOINT,
            actor=TECHNICIAN,
            occurred_at=next_time(ticket),
        )
    with pytest.raises(TransitionPreconditionError):
        ticket.reassess_priority(
            TicketImpact.ORGANIZATION,
            TicketUrgency.HIGH,
            actor=TECHNICIAN,
            occurred_at=next_time(ticket),
        )


def test_update_obeys_optimistic_version() -> None:
    ticket = new_ticket()
    with pytest.raises(StaleTicketVersionError):
        ticket.change_category(
            TicketCategory.ACCESS_APPLICATION,
            actor=TECHNICIAN,
            occurred_at=next_time(ticket),
            expected_version=99,
        )


def test_start_work_assignment_and_status_share_one_revision() -> None:
    ticket = build_ticket_at(TicketStatus.TRIAGED)
    previous_history_size = len(ticket.history)
    previous_version = ticket.version
    ticket.transition(
        TicketStatus.IN_PROGRESS,
        actor=TECHNICIAN,
        occurred_at=next_time(ticket),
        context=TransitionContext(assignee_id=TECHNICIAN.id),
    )
    new_events = ticket.history[previous_history_size:]
    assert ticket.assignee_id == TECHNICIAN.id
    assert [type(event) for event in new_events] == [TicketAssigned, TicketStatusChanged]
    assert {event.revision for event in new_events} == {previous_version + 1}


def test_resolution_and_closure_have_specific_events() -> None:
    ticket = build_ticket_at(TicketStatus.IN_PROGRESS)
    ticket.transition(
        TicketStatus.RESOLVED,
        actor=TECHNICIAN,
        occurred_at=next_time(ticket),
        context=TransitionContext(resolution_summary="Resolution verified"),
    )
    assert ticket.resolution_summary == "Resolution verified"
    assert isinstance(ticket.history[-2], TicketStatusChanged)
    assert isinstance(ticket.history[-1], TicketResolved)

    ticket.transition(
        TicketStatus.CLOSED,
        actor=REQUESTER,
        occurred_at=next_time(ticket),
        context=TransitionContext(requester_confirmed=True),
    )
    assert isinstance(ticket.history[-2], TicketStatusChanged)
    assert isinstance(ticket.history[-1], TicketClosed)


def test_events_are_immutable_and_do_not_copy_ticket_content() -> None:
    ticket = build_ticket_at(TicketStatus.RESOLVED)
    event = ticket.history[-1]
    with pytest.raises(FrozenInstanceError):
        event.revision = 99  # type: ignore[misc]
    for history_event in ticket.history:
        assert {field.name for field in fields(history_event)}.isdisjoint(
            {"title", "description", "resolution_summary", "reason"}
        )
