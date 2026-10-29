"""Ticket aggregate and its explicit state machine."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Final

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
    InvalidTimestampError,
    InvalidTransitionError,
    StaleTicketVersionError,
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
from opsbridge.domain.tickets.values import Actor, ActorId, TicketId, TicketKey

_TERMINAL_STATUSES: Final = frozenset({TicketStatus.CLOSED, TicketStatus.CANCELLED})
_ALLOWED_TRANSITIONS = MappingProxyType(
    {
        TicketStatus.NEW: frozenset({TicketStatus.TRIAGED, TicketStatus.CANCELLED}),
        TicketStatus.TRIAGED: frozenset({TicketStatus.IN_PROGRESS, TicketStatus.CANCELLED}),
        TicketStatus.IN_PROGRESS: frozenset(
            {
                TicketStatus.WAITING_APPROVAL,
                TicketStatus.WAITING_REQUESTER,
                TicketStatus.RESOLVED,
                TicketStatus.CANCELLED,
            }
        ),
        TicketStatus.WAITING_APPROVAL: frozenset(
            {TicketStatus.IN_PROGRESS, TicketStatus.CANCELLED}
        ),
        TicketStatus.WAITING_REQUESTER: frozenset(
            {TicketStatus.IN_PROGRESS, TicketStatus.CANCELLED}
        ),
        TicketStatus.RESOLVED: frozenset(
            {TicketStatus.IN_PROGRESS, TicketStatus.CLOSED, TicketStatus.CANCELLED}
        ),
        TicketStatus.CLOSED: frozenset(),
        TicketStatus.CANCELLED: frozenset(),
    }
)


@dataclass(frozen=True, slots=True)
class TransitionContext:
    """Evidence needed by specific transitions; omitted values are deliberately invalid."""

    reason: str | None = None
    assignee_id: ActorId | None = None
    approval_reference: str | None = None
    approval_resolved: bool = False
    requester_response_received: bool = False
    resolution_summary: str | None = None
    requester_confirmed: bool = False
    classification_validated: bool = False


class Ticket:
    """Framework-independent ticket aggregate with controlled mutation."""

    __slots__ = (
        "_assignee_id",
        "_category",
        "_created_at",
        "_description",
        "_history",
        "_id",
        "_impact",
        "_key",
        "_priority",
        "_requester_id",
        "_resolution_summary",
        "_status",
        "_title",
        "_updated_at",
        "_urgency",
        "_version",
    )

    _id: TicketId
    _key: TicketKey
    _title: str
    _description: str
    _category: TicketCategory
    _impact: TicketImpact
    _urgency: TicketUrgency
    _priority: TicketPriority
    _status: TicketStatus
    _created_at: datetime
    _updated_at: datetime
    _requester_id: ActorId
    _assignee_id: ActorId | None
    _resolution_summary: str | None
    _version: int
    _history: tuple[TicketEvent, ...]

    def __init__(self) -> None:
        raise TypeError("use Ticket.create()")

    @classmethod
    def create(
        cls,
        *,
        ticket_id: TicketId,
        key: TicketKey,
        title: str,
        description: str,
        category: TicketCategory,
        impact: TicketImpact,
        urgency: TicketUrgency,
        requester: Actor,
        created_at: datetime,
    ) -> "Ticket":
        if not isinstance(ticket_id, TicketId):
            raise TicketValidationError("ticket_id must be a TicketId")
        if not isinstance(key, TicketKey):
            raise TicketValidationError("key must be a TicketKey")
        if not isinstance(requester, Actor):
            raise UnauthorizedDomainOperationError("requester must be a validated Actor")
        if requester.role is not ActorRole.REQUESTER:
            raise UnauthorizedDomainOperationError("ticket creation requires a requester")
        normalized_title = _validated_text(title, "title", 5, 160)
        normalized_description = _validated_text(description, "description", 20, 4000)
        if not isinstance(category, TicketCategory):
            raise InvalidCategoryError("category must use the approved taxonomy")
        timestamp = _validated_utc(created_at)
        if key.year != timestamp.year:
            raise TicketValidationError("ticket_key year must match created_at")
        priority = calculate_priority(impact, urgency)

        self = object.__new__(cls)
        self._id = ticket_id
        self._key = key
        self._title = normalized_title
        self._description = normalized_description
        self._category = category
        self._impact = impact
        self._urgency = urgency
        self._priority = priority
        self._status = TicketStatus.NEW
        self._created_at = timestamp
        self._updated_at = timestamp
        self._requester_id = requester.id
        self._assignee_id = None
        self._resolution_summary = None
        self._version = 1
        self._history = (
            TicketCreated(
                ticket_id=ticket_id,
                ticket_key=key,
                actor=requester,
                occurred_at=timestamp,
                revision=1,
                category=category,
                priority=priority,
                priority_policy_version=PRIORITY_POLICY_VERSION,
                status=TicketStatus.NEW,
            ),
        )
        return self

    @classmethod
    def create_by_technician(
        cls,
        *,
        ticket_id: TicketId,
        key: TicketKey,
        title: str,
        description: str,
        category: TicketCategory,
        impact: TicketImpact,
        urgency: TicketUrgency,
        technician: Actor,
        created_at: datetime,
    ) -> "Ticket":
        """Create a technician-reported ticket without weakening requester creation."""

        if not isinstance(technician, Actor) or technician.role is not ActorRole.TECHNICIAN:
            raise UnauthorizedDomainOperationError("technical creation requires a technician")
        ticket = cls.create(
            ticket_id=ticket_id,
            key=key,
            title=title,
            description=description,
            category=category,
            impact=impact,
            urgency=urgency,
            requester=Actor(technician.id, ActorRole.REQUESTER),
            created_at=created_at,
        )
        creation = ticket._history[0]
        if not isinstance(creation, TicketCreated):  # pragma: no cover - constructor invariant
            raise TicketValidationError("ticket creation history is invalid")
        ticket._history = (replace(creation, actor=technician),)
        return ticket

    @classmethod
    def rehydrate(
        cls,
        *,
        ticket_id: TicketId,
        key: TicketKey,
        title: str,
        description: str,
        category: TicketCategory,
        impact: TicketImpact,
        urgency: TicketUrgency,
        priority: TicketPriority,
        status: TicketStatus,
        created_at: datetime,
        updated_at: datetime,
        requester_id: ActorId,
        assignee_id: ActorId | None,
        resolution_summary: str | None,
        version: int,
        history: tuple[TicketEvent, ...],
    ) -> "Ticket":
        """Restore a persisted aggregate without creating artificial events."""

        if not isinstance(ticket_id, TicketId) or not isinstance(key, TicketKey):
            raise TicketValidationError("persisted ticket identity is invalid")
        normalized_title = _validated_text(title, "title", 5, 160)
        normalized_description = _validated_text(description, "description", 20, 4000)
        if not isinstance(category, TicketCategory):
            raise InvalidCategoryError("persisted category is invalid")
        if not isinstance(status, TicketStatus):
            raise TicketValidationError("persisted status is invalid")
        if not isinstance(requester_id, ActorId):
            raise TicketValidationError("persisted requester is invalid")
        if assignee_id is not None and not isinstance(assignee_id, ActorId):
            raise TicketValidationError("persisted assignee is invalid")
        created = _validated_utc(created_at)
        updated = _validated_utc(updated_at)
        if updated < created:
            raise InvalidTimestampError("updated_at cannot precede created_at")
        if key.year != created.year:
            raise TicketValidationError("ticket_key year must match created_at")
        calculated_priority = calculate_priority(impact, urgency)
        if priority is not calculated_priority:
            raise TicketValidationError("persisted priority violates the active policy")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise TicketValidationError("persisted version must be a positive integer")
        if status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
            if resolution_summary is None:
                raise TicketValidationError("resolved tickets require a resolution summary")
            _validated_text(resolution_summary, "resolution_summary", 1, 4000)
        _validate_persisted_history(
            history=history,
            ticket_id=ticket_id,
            key=key,
            created_at=created,
            updated_at=updated,
            version=version,
            category=category,
            priority=priority,
            status=status,
            requester_id=requester_id,
            assignee_id=assignee_id,
        )

        self = object.__new__(cls)
        self._id = ticket_id
        self._key = key
        self._title = normalized_title
        self._description = normalized_description
        self._category = category
        self._impact = impact
        self._urgency = urgency
        self._priority = priority
        self._status = status
        self._created_at = created
        self._updated_at = updated
        self._requester_id = requester_id
        self._assignee_id = assignee_id
        self._resolution_summary = (
            resolution_summary.strip() if resolution_summary is not None else None
        )
        self._version = version
        self._history = history
        return self

    @property
    def id(self) -> TicketId:
        return self._id

    @property
    def key(self) -> TicketKey:
        return self._key

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def category(self) -> TicketCategory:
        return self._category

    @property
    def impact(self) -> TicketImpact:
        return self._impact

    @property
    def urgency(self) -> TicketUrgency:
        return self._urgency

    @property
    def priority(self) -> TicketPriority:
        return self._priority

    @property
    def status(self) -> TicketStatus:
        return self._status

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def requester_id(self) -> ActorId:
        return self._requester_id

    @property
    def assignee_id(self) -> ActorId | None:
        return self._assignee_id

    @property
    def resolution_summary(self) -> str | None:
        return self._resolution_summary

    @property
    def version(self) -> int:
        return self._version

    @property
    def history(self) -> tuple[TicketEvent, ...]:
        return self._history

    @staticmethod
    def allowed_targets(status: TicketStatus) -> frozenset[TicketStatus]:
        if not isinstance(status, TicketStatus):
            raise InvalidTransitionError("status must be an approved TicketStatus")
        return _ALLOWED_TRANSITIONS[status]

    def change_category(
        self,
        category: TicketCategory,
        *,
        actor: Actor,
        occurred_at: datetime,
        expected_version: int | None = None,
    ) -> bool:
        self._validate_common_operation(actor, occurred_at, expected_version)
        self._require_editable()
        self._require_role(actor, {ActorRole.TECHNICIAN, ActorRole.AUTOMATION})
        if not isinstance(category, TicketCategory):
            raise InvalidCategoryError("category must use the approved taxonomy")
        if category is self._category:
            return False

        previous = self._category
        revision = self._version + 1
        timestamp = _validated_utc(occurred_at)
        event = TicketCategoryChanged(
            ticket_id=self._id,
            ticket_key=self._key,
            actor=actor,
            occurred_at=timestamp,
            revision=revision,
            previous=previous,
            current=category,
        )
        self._category = category
        self._commit(timestamp, (event,))
        return True

    def reassess_priority(
        self,
        impact: TicketImpact,
        urgency: TicketUrgency,
        *,
        actor: Actor,
        occurred_at: datetime,
        expected_version: int | None = None,
    ) -> bool:
        self._validate_common_operation(actor, occurred_at, expected_version)
        self._require_editable()
        self._require_role(actor, {ActorRole.TECHNICIAN, ActorRole.AUTOMATION})
        priority = calculate_priority(impact, urgency)
        if impact is self._impact and urgency is self._urgency:
            return False

        previous = self._priority
        revision = self._version + 1
        timestamp = _validated_utc(occurred_at)
        event = TicketPriorityReassessed(
            ticket_id=self._id,
            ticket_key=self._key,
            actor=actor,
            occurred_at=timestamp,
            revision=revision,
            previous=previous,
            current=priority,
            policy_version=PRIORITY_POLICY_VERSION,
        )
        self._impact = impact
        self._urgency = urgency
        self._priority = priority
        self._commit(timestamp, (event,))
        return True

    def transition(
        self,
        target: TicketStatus,
        *,
        actor: Actor,
        occurred_at: datetime,
        context: TransitionContext | None = None,
        expected_version: int | None = None,
    ) -> bool:
        self._validate_common_operation(actor, occurred_at, expected_version)
        if not isinstance(target, TicketStatus):
            raise InvalidTransitionError("target must be an approved TicketStatus")
        if target is self._status:
            return False
        if target not in _ALLOWED_TRANSITIONS[self._status]:
            raise InvalidTransitionError(
                f"transition {self._status.value} -> {target.value} is not allowed"
            )
        transition_context = context or TransitionContext()
        if not isinstance(transition_context, TransitionContext):
            raise TransitionPreconditionError("context must be a TransitionContext")
        self._validate_transition(target, actor, transition_context)

        previous = self._status
        timestamp = _validated_utc(occurred_at)
        revision = self._version + 1
        events: list[TicketEvent] = []
        if previous is TicketStatus.TRIAGED and target is TicketStatus.IN_PROGRESS:
            if transition_context.assignee_id is None:  # protected by validation
                raise TransitionPreconditionError("assignee_id is required")
            self._assignee_id = transition_context.assignee_id
            events.append(
                TicketAssigned(
                    ticket_id=self._id,
                    ticket_key=self._key,
                    actor=actor,
                    occurred_at=timestamp,
                    revision=revision,
                    assignee_id=transition_context.assignee_id,
                )
            )
        if target is TicketStatus.RESOLVED:
            if transition_context.resolution_summary is None:  # protected by validation
                raise TransitionPreconditionError("resolution_summary is required")
            self._resolution_summary = transition_context.resolution_summary.strip()

        self._status = target
        events.append(
            TicketStatusChanged(
                ticket_id=self._id,
                ticket_key=self._key,
                actor=actor,
                occurred_at=timestamp,
                revision=revision,
                previous=previous,
                current=target,
            )
        )
        if target is TicketStatus.RESOLVED:
            events.append(TicketResolved(self._id, self._key, actor, timestamp, revision))
        elif target is TicketStatus.CLOSED:
            events.append(TicketClosed(self._id, self._key, actor, timestamp, revision))
        self._commit(timestamp, tuple(events))
        return True

    def _validate_transition(
        self, target: TicketStatus, actor: Actor, context: TransitionContext
    ) -> None:
        source = self._status
        if target is TicketStatus.CANCELLED:
            self._validate_cancellation(actor, context)
        elif source is TicketStatus.NEW and target is TicketStatus.TRIAGED:
            self._require_role(actor, {ActorRole.TECHNICIAN, ActorRole.AUTOMATION})
            if actor.role is ActorRole.AUTOMATION and not context.classification_validated:
                raise TransitionPreconditionError(
                    "automation triage requires validated classification"
                )
        elif source is TicketStatus.TRIAGED and target is TicketStatus.IN_PROGRESS:
            self._require_role(actor, {ActorRole.TECHNICIAN})
            if context.assignee_id is None:
                raise TransitionPreconditionError("starting work requires assignee_id")
        elif source is TicketStatus.IN_PROGRESS and target is TicketStatus.WAITING_APPROVAL:
            self._require_role(actor, {ActorRole.TECHNICIAN})
            _require_nonblank(context.approval_reference, "approval_reference")
        elif source is TicketStatus.WAITING_APPROVAL and target is TicketStatus.IN_PROGRESS:
            self._require_role(
                actor, {ActorRole.TECHNICIAN, ActorRole.APPROVER, ActorRole.AUTOMATION}
            )
            if not context.approval_resolved:
                raise TransitionPreconditionError("approval must be resolved or expired")
        elif source is TicketStatus.IN_PROGRESS and target is TicketStatus.WAITING_REQUESTER:
            self._require_role(actor, {ActorRole.TECHNICIAN})
            _require_nonblank(context.reason, "reason")
        elif source is TicketStatus.WAITING_REQUESTER and target is TicketStatus.IN_PROGRESS:
            self._require_requester(actor)
            if not context.requester_response_received:
                raise TransitionPreconditionError("requester response must be recorded")
        elif source is TicketStatus.IN_PROGRESS and target is TicketStatus.RESOLVED:
            self._require_role(actor, {ActorRole.TECHNICIAN})
            _require_nonblank(context.resolution_summary, "resolution_summary")
        elif source is TicketStatus.RESOLVED and target is TicketStatus.IN_PROGRESS:
            self._require_role(actor, {ActorRole.TECHNICIAN})
            _require_nonblank(context.reason, "reopen reason")
        elif source is TicketStatus.RESOLVED and target is TicketStatus.CLOSED:
            if actor.role is ActorRole.REQUESTER:
                self._require_requester(actor)
                if not context.requester_confirmed:
                    raise TransitionPreconditionError("requester confirmation is required")
            elif actor.role is ActorRole.TECHNICIAN:
                _require_nonblank(context.reason, "closure reason")
            else:
                raise UnauthorizedDomainOperationError("only requester or technician may close")

    def _validate_cancellation(self, actor: Actor, context: TransitionContext) -> None:
        if actor.role is ActorRole.REQUESTER:
            self._require_requester(actor)
            if self._status not in {TicketStatus.NEW, TicketStatus.TRIAGED}:
                raise UnauthorizedDomainOperationError(
                    "requester may cancel only before work starts"
                )
        elif actor.role is ActorRole.TECHNICIAN:
            _require_nonblank(context.reason, "cancellation reason")
        else:
            raise UnauthorizedDomainOperationError("only requester or technician may cancel")

    def _validate_common_operation(
        self, actor: Actor, occurred_at: datetime, expected_version: int | None
    ) -> None:
        if not isinstance(actor, Actor):
            raise UnauthorizedDomainOperationError("actor must be a validated Actor")
        timestamp = _validated_utc(occurred_at)
        if timestamp < self._updated_at:
            raise InvalidTimestampError("occurred_at cannot precede the last update")
        if expected_version is not None and expected_version != self._version:
            raise StaleTicketVersionError(
                f"expected version {expected_version}, current version is {self._version}"
            )

    def _require_editable(self) -> None:
        if self._status in _TERMINAL_STATUSES:
            raise TransitionPreconditionError("terminal tickets cannot be edited")

    def _require_requester(self, actor: Actor) -> None:
        self._require_role(actor, {ActorRole.REQUESTER})
        if actor.id != self._requester_id:
            raise UnauthorizedDomainOperationError("actor is not this ticket's requester")

    @staticmethod
    def _require_role(actor: Actor, allowed: set[ActorRole]) -> None:
        if actor.role not in allowed:
            raise UnauthorizedDomainOperationError(
                "actor role is not authorized for this operation"
            )

    def _commit(self, timestamp: datetime, events: tuple[TicketEvent, ...]) -> None:
        self._version += 1
        self._updated_at = timestamp
        self._history += events


def _validated_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise InvalidTimestampError("timestamps must be timezone-aware UTC values")
    return value


def _validated_text(value: str, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise TicketValidationError(f"{field} must be text")
    normalized = value.strip()
    if not minimum <= len(normalized) <= maximum:
        raise TicketValidationError(f"{field} length must be between {minimum} and {maximum}")
    return normalized


def _require_nonblank(value: str | None, field: str) -> None:
    if value is None or not value.strip():
        raise TransitionPreconditionError(f"{field} is required")


def _validate_persisted_history(
    *,
    history: tuple[TicketEvent, ...],
    ticket_id: TicketId,
    key: TicketKey,
    created_at: datetime,
    updated_at: datetime,
    version: int,
    category: TicketCategory,
    priority: TicketPriority,
    status: TicketStatus,
    requester_id: ActorId,
    assignee_id: ActorId | None,
) -> None:
    if not isinstance(history, tuple) or not history:
        raise TicketValidationError("persisted history must contain creation")
    first = history[0]
    if not isinstance(first, TicketCreated) or first.revision != 1:
        raise TicketValidationError("persisted history must begin with ticket creation")
    if first.status is not TicketStatus.NEW:
        raise TicketValidationError("persisted creation event has an invalid status")
    if (
        first.actor.role not in {ActorRole.REQUESTER, ActorRole.TECHNICIAN}
        or first.actor.id != requester_id
    ):
        raise TicketValidationError("persisted creation actor is inconsistent")
    previous_revision = 0
    previous_timestamp = created_at
    revisions: set[int] = set()
    projected_category = first.category
    projected_priority = first.priority
    projected_status: TicketStatus = first.status
    projected_assignee: ActorId | None = None
    for event in history:
        if event.ticket_id != ticket_id or event.ticket_key != key:
            raise TicketValidationError("persisted event belongs to another ticket")
        timestamp = _validated_utc(event.occurred_at)
        if timestamp < previous_timestamp or timestamp > updated_at:
            raise InvalidTimestampError("persisted event timestamps are inconsistent")
        if event.revision < previous_revision or event.revision > version:
            raise TicketValidationError("persisted event revisions are inconsistent")
        revisions.add(event.revision)
        if isinstance(event, TicketCategoryChanged):
            if event.previous is not projected_category:
                raise TicketValidationError("persisted category history is inconsistent")
            projected_category = event.current
        elif isinstance(event, TicketPriorityReassessed):
            if event.previous is not projected_priority:
                raise TicketValidationError("persisted priority history is inconsistent")
            projected_priority = event.current
        elif isinstance(event, TicketAssigned):
            projected_assignee = event.assignee_id
        elif isinstance(event, TicketStatusChanged):
            if event.previous is not projected_status:
                raise TicketValidationError("persisted status history is inconsistent")
            projected_status = event.current
        elif isinstance(event, TicketResolved) and projected_status is not TicketStatus.RESOLVED:
            raise TicketValidationError("persisted resolution event is inconsistent")
        elif isinstance(event, TicketClosed) and projected_status is not TicketStatus.CLOSED:
            raise TicketValidationError("persisted closure event is inconsistent")
        previous_revision = event.revision
        previous_timestamp = timestamp
    if (
        first.occurred_at != created_at
        or previous_timestamp != updated_at
        or previous_revision != version
        or revisions != set(range(1, version + 1))
    ):
        raise TicketValidationError("persisted history does not match ticket revision")
    if (
        projected_category is not category
        or projected_priority is not priority
        or projected_status is not status
        or projected_assignee != assignee_id
    ):
        raise TicketValidationError("persisted history does not match ticket projection")
