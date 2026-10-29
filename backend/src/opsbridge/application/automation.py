"""Governed synthetic automation: propose, approve, and execute exactly once."""

import hashlib
import hmac
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil
from time import perf_counter_ns
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from opsbridge.application.errors import (
    ActionConflictError,
    ForbiddenError,
    ResourceNotFoundError,
    SeparationOfDutiesError,
    ToolNotAllowedError,
    VersionMismatchError,
)
from opsbridge.domain.identity import LocalUser
from opsbridge.domain.tickets import ActorRole, TicketStatus
from opsbridge.infrastructure.db.automation_models import (
    ActionExecutionRecord,
    ActionProposalRecord,
    SimulatedVpnSessionRecord,
    ToolAuditRecord,
)
from opsbridge.infrastructure.db.database import Database
from opsbridge.infrastructure.db.error_translation import (
    translate_commit_error,
    translate_operational_error,
)
from opsbridge.infrastructure.db.models import TicketRecord


class VpnResetArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity_code: str = Field(pattern=r"^DEMO-VPN-[0-9]{3}$")


@dataclass(frozen=True)
class Proposal:
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


@dataclass(frozen=True)
class Execution:
    id: str
    proposal_id: str
    status: str
    result: dict[str, object]
    executed_at: datetime


class AutomationService:
    """Enforce policy independently from any future model output."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def propose_vpn_reset(
        self,
        *,
        user: LocalUser,
        ticket_id: str,
        ticket_version: int,
        identity_code: str,
        source_mode: Literal["rules"] = "rules",
    ) -> Proposal:
        if user.role is not ActorRole.TECHNICIAN:
            raise ForbiddenError
        started_at = perf_counter_ns()
        arguments = VpnResetArguments(identity_code=identity_code).model_dump()
        now = datetime.now(UTC)
        proposal_id = str(uuid4())
        with _write_session(self._database) as session:
            ticket = session.get(TicketRecord, ticket_id)
            if ticket is None:
                raise ResourceNotFoundError
            if ticket.version != ticket_version:
                raise VersionMismatchError
            if ticket.category != "network.vpn":
                raise ToolNotAllowedError
            if ticket.status != TicketStatus.IN_PROGRESS.value:
                raise ToolNotAllowedError
            if ticket.assignee_id != str(user.id):
                raise ForbiddenError
            arguments_hash = _action_hash(
                ticket_id=ticket_id,
                ticket_version=ticket_version,
                action_type="vpn_session.reset",
                arguments=arguments,
            )
            record = ActionProposalRecord(
                id=proposal_id,
                ticket_id=ticket_id,
                ticket_version=ticket_version,
                action_type="vpn_session.reset",
                source_mode=source_mode,
                arguments=arguments,
                arguments_hash=arguments_hash,
                proposer_id=str(user.id),
                status="pending_approval",
                created_at=now,
                expires_at=now + timedelta(minutes=30),
                decision_actor_id=None,
                decided_at=None,
                decision_reason=None,
            )
            session.add(record)
            session.flush()
            session.add(
                _audit(record, str(user.id), "proposal", "accepted", now, _elapsed_ms(started_at))
            )
            return _proposal(record)

    def list_proposals(self, *, user: LocalUser, status: str | None = None) -> list[Proposal]:
        if user.role not in {ActorRole.TECHNICIAN, ActorRole.APPROVER}:
            raise ForbiddenError
        statement = select(ActionProposalRecord).order_by(
            ActionProposalRecord.created_at.desc(), ActionProposalRecord.id.desc()
        )
        if user.role is ActorRole.TECHNICIAN:
            statement = statement.where(ActionProposalRecord.proposer_id == str(user.id))
        if status is not None:
            if status not in {"pending_approval", "approved", "rejected", "executed"}:
                raise ToolNotAllowedError
            statement = statement.where(ActionProposalRecord.status == status)
        with _read_session(self._database) as session:
            return [_proposal(item) for item in session.scalars(statement).all()]

    def decide(
        self,
        *,
        user: LocalUser,
        proposal_id: str,
        decision: Literal["approve", "reject"],
        reason: str,
    ) -> Proposal:
        if user.role is not ActorRole.APPROVER:
            raise ForbiddenError
        started_at = perf_counter_ns()
        now = datetime.now(UTC)
        with _write_session(self._database) as session:
            record = session.get(ActionProposalRecord, proposal_id)
            if record is None:
                raise ResourceNotFoundError
            ticket = session.get(TicketRecord, record.ticket_id)
            if ticket is None:
                raise ResourceNotFoundError
            if (
                ticket.version != record.ticket_version
                or ticket.status != TicketStatus.IN_PROGRESS.value
            ):
                raise ActionConflictError
            if str(user.id) in {record.proposer_id, ticket.requester_id}:
                raise SeparationOfDutiesError
            if record.status != "pending_approval" or record.expires_at <= now:
                raise ActionConflictError
            record.status = "approved" if decision == "approve" else "rejected"
            record.decision_actor_id = str(user.id)
            record.decided_at = now
            record.decision_reason = reason.strip()
            session.add(
                _audit(
                    record, str(user.id), "decision", record.status, now, _elapsed_ms(started_at)
                )
            )
            session.flush()
            return _proposal(record)

    def execute(self, *, user: LocalUser, proposal_id: str) -> Execution:
        if user.role is not ActorRole.TECHNICIAN:
            raise ForbiddenError
        started_at = perf_counter_ns()
        now = datetime.now(UTC)
        try:
            with self._database.session() as session:
                record = session.get(ActionProposalRecord, proposal_id)
                if record is None:
                    raise ResourceNotFoundError
                if record.proposer_id != str(user.id):
                    raise ForbiddenError
                if record.status != "approved" or record.expires_at <= now:
                    raise ActionConflictError
                ticket = session.get(TicketRecord, record.ticket_id)
                if ticket is None:
                    raise ResourceNotFoundError
                if ticket.version != record.ticket_version:
                    raise VersionMismatchError
                if ticket.status != TicketStatus.IN_PROGRESS.value:
                    raise ActionConflictError
                if ticket.assignee_id != str(user.id):
                    raise ForbiddenError
                arguments = VpnResetArguments.model_validate(record.arguments)
                expected_hash = _action_hash(
                    ticket_id=record.ticket_id,
                    ticket_version=record.ticket_version,
                    action_type=record.action_type,
                    arguments=arguments.model_dump(),
                )
                if not hmac.compare_digest(expected_hash, record.arguments_hash):
                    raise ActionConflictError
                claimed = cast_cursor_result(
                    session.execute(
                        update(ActionProposalRecord)
                        .where(
                            ActionProposalRecord.id == proposal_id,
                            ActionProposalRecord.status == "approved",
                        )
                        .values(status="executed")
                    )
                )
                if claimed.rowcount != 1:
                    raise ActionConflictError
                simulator = session.get(SimulatedVpnSessionRecord, arguments.identity_code)
                previous_state = simulator.state if simulator is not None else "locked"
                if simulator is None:
                    simulator = SimulatedVpnSessionRecord(
                        identity_code=arguments.identity_code,
                        state="active",
                        reset_count=1,
                        updated_at=now,
                    )
                    session.add(simulator)
                else:
                    simulator.state = "active"
                    simulator.reset_count += 1
                    simulator.updated_at = now
                result: dict[str, object] = {
                    "mode": "simulated",
                    "tool": "vpn_session.reset",
                    "identity_code": arguments.identity_code,
                    "previous_state": previous_state,
                    "current_state": "active",
                    "reset_count": simulator.reset_count,
                }
                execution = ActionExecutionRecord(
                    id=str(uuid4()),
                    proposal_id=proposal_id,
                    actor_id=str(user.id),
                    status="succeeded",
                    result=result,
                    executed_at=now,
                )
                session.add(execution)
                session.add(
                    _audit(
                        record, str(user.id), "execution", "succeeded", now, _elapsed_ms(started_at)
                    )
                )
                session.flush()
                return Execution(
                    id=execution.id,
                    proposal_id=execution.proposal_id,
                    status=execution.status,
                    result=execution.result,
                    executed_at=execution.executed_at,
                )
        except IntegrityError as exc:
            raise ActionConflictError from exc
        except OperationalError as exc:
            raise translate_operational_error(exc) from exc
        except SQLAlchemyError as exc:
            raise translate_commit_error(exc) from exc

    def vpn_status(self, *, user: LocalUser, identity_code: str) -> dict[str, object]:
        if user.role not in {ActorRole.TECHNICIAN, ActorRole.APPROVER}:
            raise ForbiddenError
        arguments = VpnResetArguments(identity_code=identity_code)
        with _read_session(self._database) as session:
            record = session.get(SimulatedVpnSessionRecord, arguments.identity_code)
            return {
                "mode": "simulated",
                "identity_code": arguments.identity_code,
                "state": record.state if record is not None else "locked",
                "reset_count": record.reset_count if record is not None else 0,
            }


def _action_hash(
    *, ticket_id: str, ticket_version: int, action_type: str, arguments: dict[str, object]
) -> str:
    canonical = json.dumps(
        {
            "ticket_id": ticket_id,
            "ticket_version": ticket_version,
            "action_type": action_type,
            "arguments": arguments,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _proposal(record: ActionProposalRecord) -> Proposal:
    return Proposal(
        id=record.id,
        ticket_id=record.ticket_id,
        ticket_version=record.ticket_version,
        action_type=record.action_type,
        source_mode=record.source_mode,
        arguments=record.arguments,
        arguments_hash=record.arguments_hash,
        proposer_id=record.proposer_id,
        status=record.status,
        created_at=record.created_at,
        expires_at=record.expires_at,
        decision_actor_id=record.decision_actor_id,
        decided_at=record.decided_at,
        decision_reason=record.decision_reason,
    )


def _audit(
    record: ActionProposalRecord,
    actor_id: str,
    operation: str,
    status: str,
    now: datetime,
    duration_ms: int,
) -> ToolAuditRecord:
    return ToolAuditRecord(
        proposal_id=record.id,
        action_type=record.action_type,
        actor_id=actor_id,
        operation=operation,
        status=status,
        duration_ms=duration_ms,
        created_at=now,
    )


def _elapsed_ms(started_at: int) -> int:
    """Return measured wall duration rounded up to integer milliseconds."""

    return max(1, ceil((perf_counter_ns() - started_at) / 1_000_000))


@contextmanager
def _write_session(database: Database) -> Iterator[Session]:
    try:
        with database.session() as session:
            yield session
    except OperationalError as exc:
        raise translate_operational_error(exc) from exc
    except SQLAlchemyError as exc:
        raise translate_commit_error(exc) from exc


@contextmanager
def _read_session(database: Database) -> Iterator[Session]:
    try:
        with database.create_session() as session:
            yield session
    except OperationalError as exc:
        raise translate_operational_error(exc) from exc
    except SQLAlchemyError as exc:
        raise translate_commit_error(exc) from exc


def cast_cursor_result(result: object) -> CursorResult[Any]:
    """Narrow SQLAlchemy's broad execute result for DML row-count inspection."""

    if not isinstance(result, CursorResult):
        raise ActionConflictError
    return result
