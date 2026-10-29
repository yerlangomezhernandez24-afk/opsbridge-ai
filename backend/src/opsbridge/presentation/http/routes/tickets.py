"""Authenticated ticket REST endpoints backed by application use cases."""

from datetime import datetime
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Cookie, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from opsbridge.application.auth import AuthService, SessionState
from opsbridge.application.errors import (
    AuthenticationRequiredError,
    CsrfInvalidError,
    MalformedRequestError,
    OriginNotAllowedError,
    PreconditionRequiredError,
    ResourceNotFoundError,
)
from opsbridge.application.ports.tickets import TicketListQuery, TicketSummaryQuery
from opsbridge.application.tickets import (
    CreateTicketCommand,
    PatchTicketCommand,
    TicketService,
    TransitionTicketCommand,
    decode_cursor,
    encode_cursor,
)
from opsbridge.domain.tickets import (
    Ticket,
    TicketCategory,
    TicketEvent,
    TicketId,
    TicketImpact,
    TicketPriority,
    TicketStatus,
    TicketUrgency,
)
from opsbridge.infrastructure.config import Settings
from opsbridge.presentation.http.routes.auth import SESSION_COOKIE

EnumT = TypeVar("EnumT", TicketStatus, TicketPriority, TicketCategory)


class CreateTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=5, max_length=160)
    description: str = Field(min_length=20, max_length=4000)
    category: TicketCategory
    impact: TicketImpact
    urgency: TicketUrgency


class PatchTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: TicketCategory | None = None
    impact: TicketImpact | None = None
    urgency: TicketUrgency | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "PatchTicketRequest":
        if self.category is None and self.impact is None and self.urgency is None:
            raise ValueError("at least one editable field is required")
        return self


class TransitionTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: TicketStatus
    reason: str | None = Field(default=None, max_length=500)
    requester_response_received: bool = False
    resolution_summary: str | None = Field(default=None, max_length=4000)
    requester_confirmed: bool = False


class TransitionOptionData(BaseModel):
    target: TicketStatus
    required_fields: list[str]


class TicketData(BaseModel):
    id: str
    key: str
    title: str
    description: str
    category: TicketCategory
    impact: TicketImpact
    urgency: TicketUrgency
    priority: TicketPriority
    status: TicketStatus
    created_at: datetime
    updated_at: datetime
    assignee_id: str | None
    resolution_summary: str | None
    version: int


class ResponseMeta(BaseModel):
    correlation_id: str


class TransitionOptionsEnvelope(BaseModel):
    data: list[TransitionOptionData]
    meta: ResponseMeta


class TicketEnvelope(BaseModel):
    data: TicketData
    meta: ResponseMeta


class TicketListMeta(ResponseMeta):
    page_size: int
    next_cursor: str | None
    has_more: bool


class TicketListEnvelope(BaseModel):
    data: list[TicketData]
    meta: TicketListMeta


class NamedCountData(BaseModel):
    name: str
    value: int


class DailyCountData(BaseModel):
    day: str
    value: int


class TicketSummaryData(BaseModel):
    total: int
    by_status: list[NamedCountData]
    by_priority: list[NamedCountData]
    by_category: list[NamedCountData]
    created_by_day: list[DailyCountData]


class TicketSummaryEnvelope(BaseModel):
    data: TicketSummaryData
    meta: ResponseMeta


class TimelineEventData(BaseModel):
    type: str
    actor_role: str
    occurred_at: datetime
    revision: int


class TimelineMeta(ResponseMeta):
    page_size: int
    next_revision: int | None
    has_more: bool


class TimelineEnvelope(BaseModel):
    data: list[TimelineEventData]
    meta: TimelineMeta


def create_ticket_router(
    service: TicketService, auth: AuthService, settings: Settings
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])

    def authenticate(session_token: str | None) -> SessionState:
        if not session_token:
            raise AuthenticationRequiredError
        return auth.session(session_token)

    def authenticate_mutation(
        session_token: str | None, origin: str | None, csrf_token: str | None
    ) -> SessionState:
        if not session_token:
            raise AuthenticationRequiredError
        if origin != settings.frontend_origin:
            raise OriginNotAllowedError
        if csrf_token is None or not auth.csrf_matches(session_token, csrf_token):
            raise CsrfInvalidError
        return auth.session(session_token)

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_ticket(
        payload: CreateTicketRequest,
        request: Request,
        response: Response,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        origin: str | None = Header(default=None),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> TicketEnvelope:
        state = authenticate_mutation(session_token, origin, csrf_token)
        key = _idempotency_key(idempotency_key)
        result = service.create(
            user=state.user,
            command=CreateTicketCommand(
                title=payload.title,
                description=payload.description,
                category=payload.category,
                impact=payload.impact,
                urgency=payload.urgency,
            ),
            idempotency_key=key,
        )
        response_data = TicketData.model_validate(result.response_data)
        response.headers["ETag"] = _etag(response_data.version)
        response.headers["Location"] = f"/api/v1/tickets/{result.ticket.id}"
        response.headers["Cache-Control"] = "no-store"
        if result.replayed:
            response.headers["Idempotency-Replayed"] = "true"
        return TicketEnvelope(
            data=response_data,
            meta=ResponseMeta(correlation_id=_correlation_id(request)),
        )

    @router.get("")
    def list_tickets(
        request: Request,
        response: Response,
        status_filter: str | None = Query(default=None, alias="status", max_length=256),
        priority: str | None = Query(default=None, max_length=64),
        category: str | None = Query(default=None, max_length=256),
        assignee_id: str | None = Query(default=None, max_length=128),
        query_text: str | None = Query(default=None, alias="query", min_length=1, max_length=100),
        page_size: Annotated[int, Query(ge=1, le=100)] = 25,
        cursor: str | None = Query(default=None, max_length=512),
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> TicketListEnvelope:
        state = authenticate(session_token)
        page = service.list(
            user=state.user,
            query=TicketListQuery(
                requester_id=None,
                statuses=_csv_enum(status_filter, TicketStatus),
                priorities=_csv_enum(priority, TicketPriority),
                categories=_csv_enum(category, TicketCategory),
                assignee_id=assignee_id,
                text=query_text.strip() if query_text else None,
                page_size=page_size,
                cursor=decode_cursor(cursor) if cursor else None,
            ),
        )
        response.headers["Cache-Control"] = "no-store"
        return TicketListEnvelope(
            data=[_ticket_data(ticket) for ticket in page.items],
            meta=TicketListMeta(
                page_size=page_size,
                next_cursor=encode_cursor(page.next_cursor) if page.next_cursor else None,
                has_more=page.next_cursor is not None,
                correlation_id=_correlation_id(request),
            ),
        )

    @router.get("/summary")
    def ticket_summary(
        request: Request,
        response: Response,
        status_filter: str | None = Query(default=None, alias="status", max_length=256),
        priority: str | None = Query(default=None, max_length=64),
        category: str | None = Query(default=None, max_length=256),
        assignee_id: str | None = Query(default=None, max_length=128),
        query_text: str | None = Query(default=None, alias="query", min_length=1, max_length=100),
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> TicketSummaryEnvelope:
        state = authenticate(session_token)
        summary = service.summarize(
            user=state.user,
            query=TicketSummaryQuery(
                requester_id=None,
                statuses=_csv_enum(status_filter, TicketStatus),
                priorities=_csv_enum(priority, TicketPriority),
                categories=_csv_enum(category, TicketCategory),
                assignee_id=assignee_id,
                text=query_text.strip() if query_text else None,
            ),
        )
        response.headers["Cache-Control"] = "no-store"
        return TicketSummaryEnvelope(
            data=TicketSummaryData(
                total=summary.total,
                by_status=[
                    NamedCountData(name=item.name, value=item.value) for item in summary.by_status
                ],
                by_priority=[
                    NamedCountData(name=item.name, value=item.value) for item in summary.by_priority
                ],
                by_category=[
                    NamedCountData(name=item.name, value=item.value) for item in summary.by_category
                ],
                created_by_day=[
                    DailyCountData(day=item.day, value=item.value)
                    for item in summary.created_by_day
                ],
            ),
            meta=ResponseMeta(correlation_id=_correlation_id(request)),
        )

    @router.get("/{ticket_id}")
    def get_ticket(
        ticket_id: str,
        request: Request,
        response: Response,
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> TicketEnvelope:
        state = authenticate(session_token)
        ticket = service.get(user=state.user, ticket_id=_ticket_id(ticket_id))
        response.headers["ETag"] = _etag(ticket.version)
        response.headers["Cache-Control"] = "no-store"
        return _ticket_envelope(request, ticket)

    @router.patch("/{ticket_id}")
    def patch_ticket(
        ticket_id: str,
        payload: PatchTicketRequest,
        request: Request,
        response: Response,
        if_match: str | None = Header(default=None, alias="If-Match"),
        origin: str | None = Header(default=None),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> TicketEnvelope:
        state = authenticate_mutation(session_token, origin, csrf_token)
        ticket = service.patch(
            user=state.user,
            ticket_id=_ticket_id(ticket_id),
            command=PatchTicketCommand(payload.category, payload.impact, payload.urgency),
            expected_version=_if_match(if_match),
        )
        response.headers["ETag"] = _etag(ticket.version)
        response.headers["Cache-Control"] = "no-store"
        return _ticket_envelope(request, ticket)

    @router.post("/{ticket_id}/transitions")
    def transition_ticket(
        ticket_id: str,
        payload: TransitionTicketRequest,
        request: Request,
        response: Response,
        if_match: str | None = Header(default=None, alias="If-Match"),
        origin: str | None = Header(default=None),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> TicketEnvelope:
        state = authenticate_mutation(session_token, origin, csrf_token)
        ticket = service.transition(
            user=state.user,
            ticket_id=_ticket_id(ticket_id),
            command=TransitionTicketCommand(
                target=payload.target,
                reason=payload.reason,
                requester_response_received=payload.requester_response_received,
                resolution_summary=payload.resolution_summary,
                requester_confirmed=payload.requester_confirmed,
            ),
            expected_version=_if_match(if_match),
        )
        response.headers["ETag"] = _etag(ticket.version)
        response.headers["Cache-Control"] = "no-store"
        return _ticket_envelope(request, ticket)

    @router.get("/{ticket_id}/transition-options")
    def transition_options(
        ticket_id: str,
        request: Request,
        response: Response,
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> TransitionOptionsEnvelope:
        state = authenticate(session_token)
        options = service.transition_options(user=state.user, ticket_id=_ticket_id(ticket_id))
        response.headers["Cache-Control"] = "no-store"
        return TransitionOptionsEnvelope(
            data=[
                TransitionOptionData(
                    target=option.target, required_fields=list(option.required_fields)
                )
                for option in options
            ],
            meta=ResponseMeta(correlation_id=_correlation_id(request)),
        )

    @router.get("/{ticket_id}/timeline")
    def ticket_timeline(
        ticket_id: str,
        request: Request,
        response: Response,
        page_size: Annotated[int, Query(ge=1, le=100)] = 50,
        after_revision: Annotated[int, Query(ge=0)] = 0,
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> TimelineEnvelope:
        state = authenticate(session_token)
        ticket = service.get(user=state.user, ticket_id=_ticket_id(ticket_id))
        response.headers["ETag"] = _etag(ticket.version)
        response.headers["Cache-Control"] = "no-store"
        candidates = [event for event in ticket.history if event.revision > after_revision]
        has_more = len(candidates) > page_size
        selected = candidates[:page_size]
        return TimelineEnvelope(
            data=[_event_data(event) for event in selected],
            meta=TimelineMeta(
                correlation_id=_correlation_id(request),
                page_size=page_size,
                next_revision=selected[-1].revision if has_more and selected else None,
                has_more=has_more,
            ),
        )

    return router


def _ticket_data(ticket: Ticket) -> TicketData:
    return TicketData(
        id=str(ticket.id),
        key=str(ticket.key),
        title=ticket.title,
        description=ticket.description,
        category=ticket.category,
        impact=ticket.impact,
        urgency=ticket.urgency,
        priority=ticket.priority,
        status=ticket.status,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        assignee_id=str(ticket.assignee_id) if ticket.assignee_id else None,
        resolution_summary=ticket.resolution_summary,
        version=ticket.version,
    )


def _event_data(event: TicketEvent) -> TimelineEventData:
    return TimelineEventData(
        type=type(event).__name__,
        actor_role=event.actor.role.value,
        occurred_at=event.occurred_at,
        revision=event.revision,
    )


def _ticket_envelope(request: Request, ticket: Ticket) -> TicketEnvelope:
    return TicketEnvelope(
        data=_ticket_data(ticket),
        meta=ResponseMeta(correlation_id=_correlation_id(request)),
    )


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", "unavailable"))


def _ticket_id(value: str) -> TicketId:
    try:
        return TicketId(UUID(value))
    except ValueError as exc:
        raise ResourceNotFoundError from exc


def _idempotency_key(value: str | None) -> UUID:
    if value is None:
        raise MalformedRequestError
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise MalformedRequestError from exc
    if parsed.version != 4 or str(parsed) != value.lower():
        raise MalformedRequestError
    return parsed


def _if_match(value: str | None) -> int:
    if value is None:
        raise PreconditionRequiredError
    if len(value) < 3 or value[0] != '"' or value[-1] != '"' or not value[1:-1].isdigit():
        raise MalformedRequestError
    version = int(value[1:-1])
    if version < 1:
        raise MalformedRequestError
    return version


def _etag(version: int) -> str:
    return f'"{version}"'


def _csv_enum(value: str | None, enum_type: type[EnumT]) -> tuple[EnumT, ...]:
    if value is None:
        return ()
    parts = value.split(",")
    if not parts or any(not item.strip() for item in parts):
        raise MalformedRequestError
    try:
        return tuple(enum_type(item.strip()) for item in parts)
    except ValueError as exc:
        raise MalformedRequestError from exc
