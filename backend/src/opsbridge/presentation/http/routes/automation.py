"""Authenticated HTTP boundary for governed, synthetic automation."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Cookie, Header, Query, status
from pydantic import BaseModel, ConfigDict, Field

from opsbridge.application.auth import AuthService, SessionState
from opsbridge.application.automation import AutomationService, Execution, Proposal
from opsbridge.application.errors import (
    AuthenticationRequiredError,
    CsrfInvalidError,
    MalformedRequestError,
    OriginNotAllowedError,
    PreconditionRequiredError,
)
from opsbridge.infrastructure.config import Settings
from opsbridge.presentation.http.routes.auth import SESSION_COOKIE


class ProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_code: str = Field(pattern=r"^DEMO-VPN-[0-9]{3}$")
    source_mode: Literal["rules"] = "rules"


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=500)


class ProposalData(BaseModel):
    id: str
    ticket_id: str
    ticket_version: int
    action_type: str
    source_mode: str
    arguments: dict[str, object]
    arguments_hash: str
    proposer_id: str
    status: str
    created_at: datetime
    expires_at: datetime
    decision_actor_id: str | None
    decided_at: datetime | None
    decision_reason: str | None


class ExecutionData(BaseModel):
    id: str
    proposal_id: str
    status: str
    result: dict[str, object]
    executed_at: datetime


class ProposalEnvelope(BaseModel):
    data: ProposalData


class ProposalListEnvelope(BaseModel):
    data: list[ProposalData]


class ExecutionEnvelope(BaseModel):
    data: ExecutionData


class SimulatorEnvelope(BaseModel):
    data: dict[str, object]


class AiStatusData(BaseModel):
    rules_available: bool
    retrieval_mode: str
    llm_local_available: bool
    llm_local_verified: bool
    provider: str
    status: str


class AiStatusEnvelope(BaseModel):
    data: AiStatusData


def create_automation_router(
    service: AutomationService, auth: AuthService, settings: Settings
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["governed automation"])

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

    @router.post("/tickets/{ticket_id}/action-proposals", status_code=status.HTTP_201_CREATED)
    def propose(
        ticket_id: str,
        payload: ProposalRequest,
        if_match: str | None = Header(default=None, alias="If-Match"),
        origin: str | None = Header(default=None),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> ProposalEnvelope:
        state = authenticate_mutation(session_token, origin, csrf_token)
        result = service.propose_vpn_reset(
            user=state.user,
            ticket_id=ticket_id,
            ticket_version=_if_match(if_match),
            identity_code=payload.identity_code,
            source_mode=payload.source_mode,
        )
        return ProposalEnvelope(data=_proposal_data(result))

    @router.get("/approval-requests")
    def list_proposals(
        proposal_status: str | None = Query(default=None, alias="status"),
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> ProposalListEnvelope:
        state = authenticate(session_token)
        return ProposalListEnvelope(
            data=[
                _proposal_data(item)
                for item in service.list_proposals(user=state.user, status=proposal_status)
            ]
        )

    @router.post("/approval-requests/{proposal_id}/decisions")
    def decide(
        proposal_id: str,
        payload: DecisionRequest,
        origin: str | None = Header(default=None),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> ProposalEnvelope:
        state = authenticate_mutation(session_token, origin, csrf_token)
        return ProposalEnvelope(
            data=_proposal_data(
                service.decide(
                    user=state.user,
                    proposal_id=proposal_id,
                    decision=payload.decision,
                    reason=payload.reason,
                )
            )
        )

    @router.post("/approval-requests/{proposal_id}/executions")
    def execute(
        proposal_id: str,
        origin: str | None = Header(default=None),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> ExecutionEnvelope:
        state = authenticate_mutation(session_token, origin, csrf_token)
        return ExecutionEnvelope(
            data=_execution_data(service.execute(user=state.user, proposal_id=proposal_id))
        )

    @router.get("/simulators/vpn/{identity_code}")
    def vpn_status(
        identity_code: str,
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> SimulatorEnvelope:
        state = authenticate(session_token)
        return SimulatorEnvelope(
            data=service.vpn_status(user=state.user, identity_code=identity_code)
        )

    @router.get("/ai/status")
    def ai_status(
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> AiStatusEnvelope:
        authenticate(session_token)
        return AiStatusEnvelope(
            data=AiStatusData(
                rules_available=True,
                retrieval_mode="sqlite_fts5_lexical",
                llm_local_available=False,
                llm_local_verified=False,
                provider="ollama",
                status="LOCAL_LLM_PENDING",
            )
        )

    return router


def _if_match(value: str | None) -> int:
    if value is None:
        raise PreconditionRequiredError
    if len(value) < 3 or value[0] != '"' or value[-1] != '"' or not value[1:-1].isdigit():
        raise MalformedRequestError
    version = int(value[1:-1])
    if version < 1:
        raise MalformedRequestError
    return version


def _proposal_data(item: Proposal) -> ProposalData:
    return ProposalData.model_validate(item, from_attributes=True)


def _execution_data(item: Execution) -> ExecutionData:
    return ExecutionData.model_validate(item, from_attributes=True)
