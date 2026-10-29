"""Creation invariants, taxonomy, and deterministic priority tests."""

from dataclasses import fields
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from opsbridge.domain.tickets import (
    PRIORITY_POLICY_VERSION,
    Actor,
    ActorId,
    ActorRole,
    InvalidCategoryError,
    InvalidIdentifierError,
    InvalidPriorityInputError,
    InvalidTimestampError,
    Ticket,
    TicketCategory,
    TicketCreated,
    TicketId,
    TicketImpact,
    TicketKey,
    TicketPriority,
    TicketStatus,
    TicketUrgency,
    TicketValidationError,
    UnauthorizedDomainOperationError,
    calculate_priority,
)
from tests.unit.domain.support import BASE_TIME, REQUESTER, new_ticket


@pytest.mark.parametrize(
    ("impact", "urgency", "expected"),
    [
        (TicketImpact.SINGLE_USER, TicketUrgency.LOW, TicketPriority.P4),
        (TicketImpact.SINGLE_USER, TicketUrgency.MEDIUM, TicketPriority.P3),
        (TicketImpact.SINGLE_USER, TicketUrgency.HIGH, TicketPriority.P3),
        (TicketImpact.MULTIPLE_USERS, TicketUrgency.LOW, TicketPriority.P4),
        (TicketImpact.MULTIPLE_USERS, TicketUrgency.MEDIUM, TicketPriority.P3),
        (TicketImpact.MULTIPLE_USERS, TicketUrgency.HIGH, TicketPriority.P2),
        (TicketImpact.ORGANIZATION, TicketUrgency.LOW, TicketPriority.P3),
        (TicketImpact.ORGANIZATION, TicketUrgency.MEDIUM, TicketPriority.P2),
        (TicketImpact.ORGANIZATION, TicketUrgency.HIGH, TicketPriority.P1),
    ],
)
def test_priority_matrix_is_deterministic(
    impact: TicketImpact, urgency: TicketUrgency, expected: TicketPriority
) -> None:
    assert calculate_priority(impact, urgency) is expected


@pytest.mark.parametrize(
    ("impact", "urgency"),
    [("single_user", TicketUrgency.MEDIUM), (TicketImpact.SINGLE_USER, "medium")],
)
def test_priority_rejects_untyped_inputs(impact: object, urgency: object) -> None:
    with pytest.raises(InvalidPriorityInputError):
        calculate_priority(impact, urgency)  # type: ignore[arg-type]


def test_creation_sets_identity_defaults_and_minimal_event() -> None:
    ticket = new_ticket()

    assert ticket.status is TicketStatus.NEW
    assert ticket.priority is TicketPriority.P3
    assert ticket.version == 1
    assert ticket.created_at == ticket.updated_at == BASE_TIME
    assert ticket.requester_id == REQUESTER.id
    assert ticket.assignee_id is None
    assert len(ticket.history) == 1
    event = ticket.history[0]
    assert isinstance(event, TicketCreated)
    assert event.revision == 1
    assert event.priority_policy_version == PRIORITY_POLICY_VERSION
    assert {field.name for field in fields(event)}.isdisjoint({"title", "description"})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "bad"),
        ("title", "x" * 161),
        ("description", "too short"),
        ("description", "x" * 4001),
    ],
)
def test_creation_enforces_api_text_limits(field: str, value: str) -> None:
    arguments: dict[str, object] = {
        "ticket_id": TicketId(uuid4()),
        "key": TicketKey("OPS-2026-000002"),
        "title": "Valid title",
        "description": "A sufficiently descriptive ticket body.",
        "category": TicketCategory.SOFTWARE_APPLICATION,
        "impact": TicketImpact.SINGLE_USER,
        "urgency": TicketUrgency.LOW,
        "requester": REQUESTER,
        "created_at": BASE_TIME,
    }
    arguments[field] = value
    with pytest.raises(TicketValidationError):
        Ticket.create(**arguments)  # type: ignore[arg-type]


def test_creation_normalizes_surrounding_whitespace() -> None:
    ticket = Ticket.create(
        ticket_id=TicketId(uuid4()),
        key=TicketKey("OPS-2026-000002"),
        title="  Valid title  ",
        description="  A sufficiently descriptive ticket body.  ",
        category=TicketCategory.SOFTWARE_APPLICATION,
        impact=TicketImpact.SINGLE_USER,
        urgency=TicketUrgency.LOW,
        requester=REQUESTER,
        created_at=BASE_TIME,
    )
    assert ticket.title == "Valid title"
    assert ticket.description == "A sufficiently descriptive ticket body."


@pytest.mark.parametrize("value", ["OPS-26-000001", "ops-2026-000001", "OPS-2026-1"])
def test_ticket_key_format_is_strict(value: str) -> None:
    with pytest.raises(InvalidIdentifierError):
        TicketKey(value)


def test_ticket_key_year_matches_creation_year() -> None:
    with pytest.raises(TicketValidationError, match="year"):
        Ticket.create(
            ticket_id=TicketId(uuid4()),
            key=TicketKey("OPS-2025-000001"),
            title="Valid title",
            description="A sufficiently descriptive ticket body.",
            category=TicketCategory.SOFTWARE_APPLICATION,
            impact=TicketImpact.SINGLE_USER,
            urgency=TicketUrgency.LOW,
            requester=REQUESTER,
            created_at=BASE_TIME,
        )


def test_ticket_id_requires_uuid_v4() -> None:
    with pytest.raises(InvalidIdentifierError):
        TicketId(UUID("12345678-1234-1234-8234-123456789abc"))


def test_creation_requires_utc() -> None:
    with pytest.raises(InvalidTimestampError):
        Ticket.create(
            ticket_id=TicketId(uuid4()),
            key=TicketKey("OPS-2026-000002"),
            title="Valid title",
            description="A sufficiently descriptive ticket body.",
            category=TicketCategory.SOFTWARE_APPLICATION,
            impact=TicketImpact.SINGLE_USER,
            urgency=TicketUrgency.LOW,
            requester=REQUESTER,
            created_at=datetime(2026, 10, 28, 12, 0),
        )


def test_creation_requires_requester_role() -> None:
    technician = Actor(ActorId("technician-02"), ActorRole.TECHNICIAN)
    with pytest.raises(UnauthorizedDomainOperationError):
        Ticket.create(
            ticket_id=TicketId(uuid4()),
            key=TicketKey("OPS-2026-000002"),
            title="Valid title",
            description="A sufficiently descriptive ticket body.",
            category=TicketCategory.SOFTWARE_APPLICATION,
            impact=TicketImpact.SINGLE_USER,
            urgency=TicketUrgency.LOW,
            requester=technician,
            created_at=datetime(2026, 10, 28, 12, 0, tzinfo=UTC),
        )


def test_creation_rejects_category_string() -> None:
    with pytest.raises(InvalidCategoryError):
        Ticket.create(
            ticket_id=TicketId(uuid4()),
            key=TicketKey("OPS-2026-000002"),
            title="Valid title",
            description="A sufficiently descriptive ticket body.",
            category="network.vpn",  # type: ignore[arg-type]
            impact=TicketImpact.SINGLE_USER,
            urgency=TicketUrgency.LOW,
            requester=REQUESTER,
            created_at=BASE_TIME,
        )


@pytest.mark.parametrize(
    ("category", "impact", "urgency", "priority"),
    [
        (
            TicketCategory.NETWORK_VPN,
            TicketImpact.SINGLE_USER,
            TicketUrgency.MEDIUM,
            TicketPriority.P3,
        ),
        (
            TicketCategory.SOFTWARE_APPLICATION,
            TicketImpact.MULTIPLE_USERS,
            TicketUrgency.HIGH,
            TicketPriority.P2,
        ),
        (
            TicketCategory.HARDWARE_ENDPOINT,
            TicketImpact.SINGLE_USER,
            TicketUrgency.LOW,
            TicketPriority.P4,
        ),
        (
            TicketCategory.ACCESS_APPLICATION,
            TicketImpact.ORGANIZATION,
            TicketUrgency.HIGH,
            TicketPriority.P1,
        ),
    ],
)
def test_initial_scenarios_cover_approved_categories(
    category: TicketCategory,
    impact: TicketImpact,
    urgency: TicketUrgency,
    priority: TicketPriority,
) -> None:
    ticket = Ticket.create(
        ticket_id=TicketId(uuid4()),
        key=TicketKey("OPS-2026-000002"),
        title="Valid scenario ticket",
        description="A sufficiently descriptive scenario ticket body.",
        category=category,
        impact=impact,
        urgency=urgency,
        requester=REQUESTER,
        created_at=BASE_TIME,
    )
    assert ticket.category is category
    assert ticket.priority is priority
