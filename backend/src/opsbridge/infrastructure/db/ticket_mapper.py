"""Bidirectional mapping between ticket domain objects and SQLAlchemy records."""

from collections.abc import Sequence
from uuid import UUID

from opsbridge.domain.tickets import (
    Actor,
    ActorId,
    ActorRole,
    Ticket,
    TicketAssigned,
    TicketCategory,
    TicketCategoryChanged,
    TicketClosed,
    TicketCreated,
    TicketDomainError,
    TicketEvent,
    TicketId,
    TicketImpact,
    TicketKey,
    TicketPriority,
    TicketPriorityReassessed,
    TicketResolved,
    TicketStatus,
    TicketStatusChanged,
    TicketUrgency,
)
from opsbridge.infrastructure.db.errors import CorruptPersistenceDataError
from opsbridge.infrastructure.db.models import TicketEventRecord, TicketRecord


def ticket_to_record(ticket: Ticket) -> TicketRecord:
    return TicketRecord(**ticket_values(ticket))


def ticket_values(ticket: Ticket) -> dict[str, object]:
    return {
        "id": str(ticket.id),
        "key": str(ticket.key),
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category.value,
        "impact": ticket.impact.value,
        "urgency": ticket.urgency.value,
        "priority": ticket.priority.value,
        "status": ticket.status.value,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "requester_id": str(ticket.requester_id),
        "assignee_id": str(ticket.assignee_id) if ticket.assignee_id is not None else None,
        "resolution_summary": ticket.resolution_summary,
        "version": ticket.version,
    }


def event_to_record(event: TicketEvent, event_order: int) -> TicketEventRecord:
    event_type: str
    payload: dict[str, object]
    if isinstance(event, TicketCreated):
        event_type = "ticket_created"
        payload = {
            "category": event.category.value,
            "priority": event.priority.value,
            "priority_policy_version": event.priority_policy_version,
            "status": event.status.value,
        }
    elif isinstance(event, TicketCategoryChanged):
        event_type = "ticket_category_changed"
        payload = {"previous": event.previous.value, "current": event.current.value}
    elif isinstance(event, TicketPriorityReassessed):
        event_type = "ticket_priority_reassessed"
        payload = {
            "previous": event.previous.value,
            "current": event.current.value,
            "policy_version": event.policy_version,
        }
    elif isinstance(event, TicketAssigned):
        event_type = "ticket_assigned"
        payload = {"assignee_id": str(event.assignee_id)}
    elif isinstance(event, TicketStatusChanged):
        event_type = "ticket_status_changed"
        payload = {"previous": event.previous.value, "current": event.current.value}
    elif isinstance(event, TicketResolved):
        event_type = "ticket_resolved"
        payload = {}
    elif isinstance(event, TicketClosed):
        event_type = "ticket_closed"
        payload = {}
    else:  # pragma: no cover - closed union protects normal calls
        raise TypeError("unsupported ticket event")
    return TicketEventRecord(
        ticket_id=str(event.ticket_id),
        event_order=event_order,
        event_type=event_type,
        actor_id=str(event.actor.id),
        actor_role=event.actor.role.value,
        occurred_at=event.occurred_at,
        revision=event.revision,
        payload=payload,
    )


def record_to_ticket(record: TicketRecord, event_records: Sequence[TicketEventRecord]) -> Ticket:
    try:
        ticket_id = TicketId(UUID(record.id))
        key = TicketKey(record.key)
        history = tuple(record_to_event(item, ticket_id, key) for item in event_records)
        return Ticket.rehydrate(
            ticket_id=ticket_id,
            key=key,
            title=record.title,
            description=record.description,
            category=TicketCategory(record.category),
            impact=TicketImpact(record.impact),
            urgency=TicketUrgency(record.urgency),
            priority=TicketPriority(record.priority),
            status=TicketStatus(record.status),
            created_at=record.created_at,
            updated_at=record.updated_at,
            requester_id=ActorId(record.requester_id),
            assignee_id=ActorId(record.assignee_id) if record.assignee_id else None,
            resolution_summary=record.resolution_summary,
            version=record.version,
            history=history,
        )
    except (KeyError, TypeError, ValueError, TicketDomainError) as exc:
        raise CorruptPersistenceDataError("persisted ticket data failed domain validation") from exc


def record_to_event(record: TicketEventRecord, ticket_id: TicketId, key: TicketKey) -> TicketEvent:
    try:
        actor = Actor(ActorId(record.actor_id), ActorRole(record.actor_role))
        payload = record.payload
        if record.event_type == "ticket_created":
            return TicketCreated(
                ticket_id=ticket_id,
                ticket_key=key,
                actor=actor,
                occurred_at=record.occurred_at,
                revision=record.revision,
                category=TicketCategory(_payload_string(payload, "category")),
                priority=TicketPriority(_payload_string(payload, "priority")),
                priority_policy_version=_payload_string(payload, "priority_policy_version"),
                status=TicketStatus(_payload_string(payload, "status")),
            )
        if record.event_type == "ticket_category_changed":
            return TicketCategoryChanged(
                ticket_id=ticket_id,
                ticket_key=key,
                actor=actor,
                occurred_at=record.occurred_at,
                revision=record.revision,
                previous=TicketCategory(_payload_string(payload, "previous")),
                current=TicketCategory(_payload_string(payload, "current")),
            )
        if record.event_type == "ticket_priority_reassessed":
            return TicketPriorityReassessed(
                ticket_id=ticket_id,
                ticket_key=key,
                actor=actor,
                occurred_at=record.occurred_at,
                revision=record.revision,
                previous=TicketPriority(_payload_string(payload, "previous")),
                current=TicketPriority(_payload_string(payload, "current")),
                policy_version=_payload_string(payload, "policy_version"),
            )
        if record.event_type == "ticket_assigned":
            return TicketAssigned(
                ticket_id=ticket_id,
                ticket_key=key,
                actor=actor,
                occurred_at=record.occurred_at,
                revision=record.revision,
                assignee_id=ActorId(_payload_string(payload, "assignee_id")),
            )
        if record.event_type == "ticket_status_changed":
            return TicketStatusChanged(
                ticket_id=ticket_id,
                ticket_key=key,
                actor=actor,
                occurred_at=record.occurred_at,
                revision=record.revision,
                previous=TicketStatus(_payload_string(payload, "previous")),
                current=TicketStatus(_payload_string(payload, "current")),
            )
        if record.event_type == "ticket_resolved":
            return TicketResolved(
                ticket_id=ticket_id,
                ticket_key=key,
                actor=actor,
                occurred_at=record.occurred_at,
                revision=record.revision,
            )
        if record.event_type == "ticket_closed":
            return TicketClosed(
                ticket_id=ticket_id,
                ticket_key=key,
                actor=actor,
                occurred_at=record.occurred_at,
                revision=record.revision,
            )
        raise ValueError("unknown persisted event type")
    except (KeyError, TypeError, ValueError, TicketDomainError) as exc:
        raise CorruptPersistenceDataError(
            "persisted ticket event failed domain validation"
        ) from exc


def _payload_string(payload: dict[str, object], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise TypeError("event payload value must be text")
    return value
