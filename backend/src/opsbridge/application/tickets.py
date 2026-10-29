"""Ticket API use cases with authorization, transactions, and idempotency."""

import base64
import binascii
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from opsbridge.application.authorization import AuthorizationPolicy, Permission
from opsbridge.application.errors import (
    ForbiddenError,
    IdempotencyConflictError,
    ResourceNotFoundError,
    VersionMismatchError,
)
from opsbridge.application.ports.tickets import (
    TicketCursor,
    TicketListQuery,
    TicketPage,
    TicketSummary,
    TicketSummaryQuery,
    TicketUnitOfWork,
)
from opsbridge.domain.identity import LocalUser
from opsbridge.domain.tickets import (
    Actor,
    ActorRole,
    Ticket,
    TicketCategory,
    TicketId,
    TicketImpact,
    TicketStatus,
    TicketUrgency,
    TransitionContext,
)

_CREATE_OPERATION = "tickets.create.v1"


@dataclass(frozen=True, slots=True)
class CreateTicketCommand:
    title: str
    description: str
    category: TicketCategory
    impact: TicketImpact
    urgency: TicketUrgency


@dataclass(frozen=True, slots=True)
class PatchTicketCommand:
    category: TicketCategory | None
    impact: TicketImpact | None
    urgency: TicketUrgency | None


@dataclass(frozen=True, slots=True)
class TransitionTicketCommand:
    target: TicketStatus
    reason: str | None = None
    requester_response_received: bool = False
    resolution_summary: str | None = None
    requester_confirmed: bool = False


@dataclass(frozen=True, slots=True)
class TransitionOption:
    target: TicketStatus
    required_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CreateTicketResult:
    ticket: Ticket
    replayed: bool
    response_data: dict[str, object]


class TicketService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], TicketUnitOfWork],
        now: Callable[[], datetime],
        new_uuid: Callable[[], UUID],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._now = now
        self._new_uuid = new_uuid
        self._authorization = AuthorizationPolicy()

    def create(
        self, *, user: LocalUser, command: CreateTicketCommand, idempotency_key: UUID
    ) -> CreateTicketResult:
        if not self._authorization.can_create_ticket(user):
            raise ForbiddenError
        now = self._now()
        request_hash = _creation_hash(command)
        scope = str(user.id)
        key = str(idempotency_key)
        with self._unit_of_work_factory() as unit:
            unit.idempotency.delete_expired(now)
            stored = unit.idempotency.get(user_id=scope, operation=_CREATE_OPERATION, key=key)
            if stored is not None:
                return self._replay(
                    unit,
                    stored.request_hash,
                    stored.ticket_id,
                    stored.response_json,
                    request_hash,
                )
            reserved = unit.idempotency.reserve(
                user_id=scope,
                operation=_CREATE_OPERATION,
                key=key,
                request_hash=request_hash,
                created_at=now,
                expires_at=now + timedelta(hours=24),
            )
            if not reserved:
                stored = unit.idempotency.get(user_id=scope, operation=_CREATE_OPERATION, key=key)
                if stored is None:
                    raise IdempotencyConflictError
                return self._replay(
                    unit,
                    stored.request_hash,
                    stored.ticket_id,
                    stored.response_json,
                    request_hash,
                )
            ticket_id = TicketId(self._new_uuid())
            public_key = unit.keys.next_key(now)
            if user.role is ActorRole.TECHNICIAN:
                ticket = Ticket.create_by_technician(
                    ticket_id=ticket_id,
                    key=public_key,
                    title=command.title,
                    description=command.description,
                    category=command.category,
                    impact=command.impact,
                    urgency=command.urgency,
                    technician=Actor(user.actor_id, user.role),
                    created_at=now,
                )
            else:
                ticket = Ticket.create(
                    ticket_id=ticket_id,
                    key=public_key,
                    title=command.title,
                    description=command.description,
                    category=command.category,
                    impact=command.impact,
                    urgency=command.urgency,
                    requester=Actor(user.actor_id, user.role),
                    created_at=now,
                )
            unit.tickets.add(ticket)
            response_data = _ticket_snapshot(ticket)
            unit.idempotency.complete(
                user_id=scope,
                operation=_CREATE_OPERATION,
                key=key,
                ticket_id=ticket.id,
                response_json=response_data,
            )
            unit.commit()
        return CreateTicketResult(
            ticket=ticket,
            replayed=False,
            response_data=response_data,
        )

    def get(self, *, user: LocalUser, ticket_id: TicketId) -> Ticket:
        with self._unit_of_work_factory() as unit:
            ticket = unit.tickets.find_by_id(ticket_id)
            return self._visible_or_not_found(user, ticket)

    def list(self, *, user: LocalUser, query: TicketListQuery) -> TicketPage:
        if Permission.TICKET_VIEW not in self._authorization.permissions_for(user):
            raise ForbiddenError
        requester_id = str(user.actor_id) if user.role is ActorRole.REQUESTER else None
        scoped = TicketListQuery(
            requester_id=requester_id,
            statuses=query.statuses,
            priorities=query.priorities,
            categories=query.categories,
            assignee_id=query.assignee_id,
            text=query.text,
            page_size=query.page_size,
            cursor=query.cursor,
        )
        with self._unit_of_work_factory() as unit:
            return unit.tickets.list(scoped)

    def summarize(self, *, user: LocalUser, query: TicketSummaryQuery) -> TicketSummary:
        if Permission.TICKET_VIEW not in self._authorization.permissions_for(user):
            raise ForbiddenError
        requester_id = str(user.actor_id) if user.role is ActorRole.REQUESTER else None
        scoped = TicketSummaryQuery(
            requester_id=requester_id,
            statuses=query.statuses,
            priorities=query.priorities,
            categories=query.categories,
            assignee_id=query.assignee_id,
            text=query.text,
        )
        with self._unit_of_work_factory() as unit:
            return unit.tickets.summarize(scoped)

    def patch(
        self,
        *,
        user: LocalUser,
        ticket_id: TicketId,
        command: PatchTicketCommand,
        expected_version: int,
    ) -> Ticket:
        with self._unit_of_work_factory() as unit:
            ticket = self._visible_or_not_found(user, unit.tickets.find_by_id(ticket_id))
            if ticket.version != expected_version:
                raise VersionMismatchError
            if user.role is not ActorRole.TECHNICIAN or not self._authorization.can_modify_ticket(
                user, ticket
            ):
                raise ForbiddenError
            if ticket.assignee_id is not None and ticket.assignee_id != user.actor_id:
                raise ForbiddenError
            before = ticket.version
            actor = Actor(user.actor_id, user.role)
            now = self._now()
            if command.category is not None:
                ticket.change_category(command.category, actor=actor, occurred_at=now)
            if command.impact is not None or command.urgency is not None:
                ticket.reassess_priority(
                    command.impact or ticket.impact,
                    command.urgency or ticket.urgency,
                    actor=actor,
                    occurred_at=now,
                )
            if ticket.version != before:
                unit.tickets.save(ticket, expected_version=before)
                unit.commit()
            return ticket

    def transition(
        self,
        *,
        user: LocalUser,
        ticket_id: TicketId,
        command: TransitionTicketCommand,
        expected_version: int,
    ) -> Ticket:
        with self._unit_of_work_factory() as unit:
            ticket = self._visible_or_not_found(user, unit.tickets.find_by_id(ticket_id))
            if ticket.version != expected_version:
                raise VersionMismatchError
            if user.role is ActorRole.APPROVER:
                raise ForbiddenError
            if user.role is ActorRole.TECHNICIAN and (
                ticket.assignee_id is not None and ticket.assignee_id != user.actor_id
            ):
                raise ForbiddenError
            # The generic waiting-approval state has no persisted evidence contract yet.
            # It is deliberately unavailable through the public API rather than trusting
            # an approval flag or arbitrary reference supplied by the client.
            if command.target is TicketStatus.WAITING_APPROVAL or (
                ticket.status is TicketStatus.WAITING_APPROVAL
                and command.target is TicketStatus.IN_PROGRESS
            ):
                raise ForbiddenError
            actor = Actor(user.actor_id, user.role)
            context = TransitionContext(
                reason=command.reason,
                assignee_id=(user.actor_id if command.target is TicketStatus.IN_PROGRESS else None),
                requester_response_received=command.requester_response_received,
                resolution_summary=command.resolution_summary,
                requester_confirmed=command.requester_confirmed,
            )
            before = ticket.version
            ticket.transition(
                command.target,
                actor=actor,
                occurred_at=self._now(),
                context=context,
                expected_version=expected_version,
            )
            if ticket.version != before:
                unit.tickets.save(ticket, expected_version=before)
                unit.commit()
            return ticket

    def transition_options(
        self, *, user: LocalUser, ticket_id: TicketId
    ) -> tuple[TransitionOption, ...]:
        with self._unit_of_work_factory() as unit:
            ticket = self._visible_or_not_found(user, unit.tickets.find_by_id(ticket_id))
        if user.role is ActorRole.APPROVER:
            return ()
        if user.role is ActorRole.TECHNICIAN and (
            ticket.assignee_id is not None and ticket.assignee_id != user.actor_id
        ):
            return ()
        return _transition_options(ticket, user)

    def _visible_or_not_found(self, user: LocalUser, ticket: Ticket | None) -> Ticket:
        if ticket is None or not self._authorization.can_view_ticket(user, ticket):
            raise ResourceNotFoundError
        return ticket

    @staticmethod
    def _replay(
        unit: TicketUnitOfWork,
        stored_hash: str,
        ticket_id: TicketId | None,
        response_json: dict[str, object] | None,
        request_hash: str,
    ) -> CreateTicketResult:
        if stored_hash != request_hash or ticket_id is None or response_json is None:
            raise IdempotencyConflictError
        ticket = unit.tickets.find_by_id(ticket_id)
        if ticket is None:
            raise IdempotencyConflictError
        return CreateTicketResult(
            ticket=ticket,
            replayed=True,
            response_data=response_json,
        )


def encode_cursor(cursor: TicketCursor) -> str:
    payload = json.dumps(
        {"created_at": cursor.created_at.isoformat(), "id": str(cursor.ticket_id)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(value: str) -> TicketCursor:
    try:
        padding = "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(value + padding))
        if not isinstance(payload, dict) or set(payload) != {"created_at", "id"}:
            raise ValueError
        created_at = datetime.fromisoformat(payload["created_at"])
        ticket_id = TicketId(UUID(payload["id"]))
        if created_at.tzinfo is None or created_at.utcoffset() != timedelta(0):
            raise ValueError
        return TicketCursor(created_at=created_at, ticket_id=ticket_id)
    except (binascii.Error, TypeError, ValueError, json.JSONDecodeError) as exc:
        from opsbridge.application.errors import MalformedRequestError

        raise MalformedRequestError from exc


def _transition_options(ticket: Ticket, user: LocalUser) -> tuple[TransitionOption, ...]:
    requester: dict[TicketStatus, tuple[TransitionOption, ...]] = {
        TicketStatus.NEW: (TransitionOption(TicketStatus.CANCELLED),),
        TicketStatus.TRIAGED: (TransitionOption(TicketStatus.CANCELLED),),
        TicketStatus.WAITING_REQUESTER: (
            TransitionOption(TicketStatus.IN_PROGRESS, ("requester_response_received",)),
        ),
        TicketStatus.RESOLVED: (TransitionOption(TicketStatus.CLOSED, ("requester_confirmed",)),),
    }
    technician: dict[TicketStatus, tuple[TransitionOption, ...]] = {
        TicketStatus.NEW: (
            TransitionOption(TicketStatus.TRIAGED),
            TransitionOption(TicketStatus.CANCELLED, ("reason",)),
        ),
        TicketStatus.TRIAGED: (
            TransitionOption(TicketStatus.IN_PROGRESS),
            TransitionOption(TicketStatus.CANCELLED, ("reason",)),
        ),
        TicketStatus.IN_PROGRESS: (
            TransitionOption(TicketStatus.WAITING_REQUESTER, ("reason",)),
            TransitionOption(TicketStatus.RESOLVED, ("resolution_summary",)),
            TransitionOption(TicketStatus.CANCELLED, ("reason",)),
        ),
        TicketStatus.WAITING_APPROVAL: (TransitionOption(TicketStatus.CANCELLED, ("reason",)),),
        TicketStatus.WAITING_REQUESTER: (TransitionOption(TicketStatus.CANCELLED, ("reason",)),),
        TicketStatus.RESOLVED: (
            TransitionOption(TicketStatus.IN_PROGRESS, ("reason",)),
            TransitionOption(TicketStatus.CLOSED, ("reason",)),
            TransitionOption(TicketStatus.CANCELLED, ("reason",)),
        ),
    }
    if user.role is ActorRole.REQUESTER:
        if ticket.requester_id != user.actor_id:
            return ()
        return requester.get(ticket.status, ())
    if user.role is ActorRole.TECHNICIAN:
        return technician.get(ticket.status, ())
    return ()


def _creation_hash(command: CreateTicketCommand) -> str:
    canonical = json.dumps(
        {
            "category": command.category.value,
            "description": command.description.strip(),
            "impact": command.impact.value,
            "title": command.title.strip(),
            "urgency": command.urgency.value,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _ticket_snapshot(ticket: Ticket) -> dict[str, object]:
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
        "created_at": ticket.created_at.isoformat(),
        "updated_at": ticket.updated_at.isoformat(),
        "assignee_id": None,
        "resolution_summary": None,
        "version": ticket.version,
    }
