"""Governed synthetic automation policy and HTTP integration tests."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import cast
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import func, select

from opsbridge.application.auth import AuthService
from opsbridge.domain.tickets import ActorRole
from opsbridge.infrastructure.config import Settings
from opsbridge.infrastructure.db import Base, Database, TicketRecord
from opsbridge.infrastructure.db.automation_models import (
    ActionExecutionRecord,
    SimulatedVpnSessionRecord,
    ToolAuditRecord,
)
from opsbridge.presentation.http.app import create_app

ORIGIN = "http://127.0.0.1:5173"
PASSWORD = "automation-test-password"  # noqa: S105
VPN_PAYLOAD = {
    "title": "Synthetic VPN session is locked",
    "description": "The DEMO VPN identity cannot establish its synthetic local session.",
    "category": "network.vpn",
    "impact": "single_user",
    "urgency": "medium",
}


@pytest.fixture
def automation_application(test_settings: Settings) -> Iterator[FastAPI]:
    application = create_app(test_settings)
    Base.metadata.create_all(application.state.database.engine)
    for login, role in (
        ("requester-one", ActorRole.REQUESTER),
        ("technician-one", ActorRole.TECHNICIAN),
        ("approver-one", ActorRole.APPROVER),
    ):
        auth: AuthService = application.state.auth_service
        auth.create_user(
            login_id=login,
            display_name=f"Synthetic {login}",
            role=role,
            password=PASSWORD,
        )
    yield application
    application.state.database.dispose()


def _login(client: TestClient, login: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"login_id": login, "password": PASSWORD},
    )
    assert response.status_code == 204
    return cast(str, client.get("/api/v1/auth/session").json()["csrf_token"])


def _headers(csrf: str, **extra: str) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": csrf, **extra}


def _create_ticket(client: TestClient, csrf: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/tickets",
        headers=_headers(csrf, **{"Idempotency-Key": str(uuid4())}),
        json=VPN_PAYLOAD,
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json()["data"])


def _propose(client: TestClient, csrf: str, ticket_id: str, version: int = 1) -> Response:
    return client.post(
        f"/api/v1/tickets/{ticket_id}/action-proposals",
        headers=_headers(csrf, **{"If-Match": f'"{version}"'}),
        json={"identity_code": "DEMO-VPN-001", "source_mode": "rules"},
    )


def _start_work(client: TestClient, csrf: str, ticket_id: str) -> int:
    triaged = client.post(
        f"/api/v1/tickets/{ticket_id}/transitions",
        headers=_headers(csrf, **{"If-Match": '"1"'}),
        json={"target": "triaged"},
    )
    assert triaged.status_code == 200
    started = client.post(
        f"/api/v1/tickets/{ticket_id}/transitions",
        headers=_headers(csrf, **{"If-Match": triaged.headers["etag"]}),
        json={"target": "in_progress"},
    )
    assert started.status_code == 200
    return cast(int, started.json()["data"]["version"])


def test_approved_proposal_executes_once_with_auditable_synthetic_effect(
    automation_application: FastAPI,
) -> None:
    with (
        TestClient(automation_application) as requester,
        TestClient(automation_application) as technician,
        TestClient(automation_application) as approver,
    ):
        requester_csrf = _login(requester, "requester-one")
        technician_csrf = _login(technician, "technician-one")
        approver_csrf = _login(approver, "approver-one")
        ticket = _create_ticket(requester, requester_csrf)
        ticket_id = cast(str, ticket["id"])
        version = _start_work(technician, technician_csrf, ticket_id)

        proposed = _propose(technician, technician_csrf, ticket_id, version)
        assert proposed.status_code == 201
        proposal = proposed.json()["data"]
        assert proposal["status"] == "pending_approval"
        assert proposal["source_mode"] == "rules"
        assert len(proposal["arguments_hash"]) == 64

        decision = approver.post(
            f"/api/v1/approval-requests/{proposal['id']}/decisions",
            headers=_headers(approver_csrf),
            json={"decision": "approve", "reason": "Validated synthetic recovery."},
        )
        assert decision.status_code == 200
        assert decision.json()["data"]["status"] == "approved"

        executed = technician.post(
            f"/api/v1/approval-requests/{proposal['id']}/executions",
            headers=_headers(technician_csrf),
        )
        repeated = technician.post(
            f"/api/v1/approval-requests/{proposal['id']}/executions",
            headers=_headers(technician_csrf),
        )
        status_response = technician.get("/api/v1/simulators/vpn/DEMO-VPN-001")

        assert executed.status_code == 200
        assert executed.json()["data"]["result"]["mode"] == "simulated"
        assert repeated.status_code == 409
        assert repeated.json()["code"] == "ACTION_CONFLICT"
        assert status_response.json()["data"] == {
            "mode": "simulated",
            "identity_code": "DEMO-VPN-001",
            "state": "active",
            "reset_count": 1,
        }

    database: Database = automation_application.state.database
    with database.create_session() as session:
        assert session.scalar(select(func.count()).select_from(ActionExecutionRecord)) == 1
        assert session.scalar(select(func.count()).select_from(ToolAuditRecord)) == 3
        durations = session.scalars(select(ToolAuditRecord.duration_ms)).all()
        assert durations and all(duration >= 1 for duration in durations)


def test_policy_denials_stale_version_and_truthful_ai_status(
    automation_application: FastAPI,
) -> None:
    with (
        TestClient(automation_application) as requester,
        TestClient(automation_application) as technician,
        TestClient(automation_application) as approver,
    ):
        requester_csrf = _login(requester, "requester-one")
        technician_csrf = _login(technician, "technician-one")
        approver_csrf = _login(approver, "approver-one")
        ticket = _create_ticket(requester, requester_csrf)
        ticket_id = cast(str, ticket["id"])

        requester_denied = _propose(requester, requester_csrf, ticket_id)
        wrong_state = _propose(technician, technician_csrf, ticket_id)
        invalid_identity = technician.post(
            f"/api/v1/tickets/{ticket_id}/action-proposals",
            headers=_headers(technician_csrf, **{"If-Match": '"1"'}),
            json={"identity_code": "../../real-account", "source_mode": "rules"},
        )
        version = _start_work(technician, technician_csrf, ticket_id)
        proposed = _propose(technician, technician_csrf, ticket_id, version)
        proposal_id = proposed.json()["data"]["id"]
        technician_approval = technician.post(
            f"/api/v1/approval-requests/{proposal_id}/decisions",
            headers=_headers(technician_csrf),
            json={"decision": "approve", "reason": "Not allowed."},
        )
        approved = approver.post(
            f"/api/v1/approval-requests/{proposal_id}/decisions",
            headers=_headers(approver_csrf),
            json={"decision": "approve", "reason": "Approved by separate role."},
        )
        assert approved.status_code == 200

        database: Database = automation_application.state.database
        with database.session() as session:
            record = session.get(TicketRecord, ticket_id)
            assert record is not None
            record.version += 1
        stale = technician.post(
            f"/api/v1/approval-requests/{proposal_id}/executions",
            headers=_headers(technician_csrf),
        )
        simulator = technician.get("/api/v1/simulators/vpn/DEMO-VPN-001")
        ai_status = technician.get("/api/v1/ai/status")

        assert requester_denied.status_code == technician_approval.status_code == 403
        assert wrong_state.status_code == 422
        assert wrong_state.json()["code"] == "TOOL_NOT_ALLOWED"
        assert invalid_identity.status_code == 422
        assert stale.status_code == 412
        assert simulator.json()["data"]["reset_count"] == 0
        assert ai_status.json()["data"] == {
            "rules_available": True,
            "retrieval_mode": "sqlite_fts5_lexical",
            "llm_local_available": False,
            "llm_local_verified": False,
            "provider": "ollama",
            "status": "LOCAL_LLM_PENDING",
        }


def test_two_concurrent_execution_attempts_have_one_effect(
    automation_application: FastAPI,
) -> None:
    with (
        TestClient(automation_application) as requester,
        TestClient(automation_application) as technician,
        TestClient(automation_application) as approver,
    ):
        requester_csrf = _login(requester, "requester-one")
        technician_csrf = _login(technician, "technician-one")
        approver_csrf = _login(approver, "approver-one")
        ticket = _create_ticket(requester, requester_csrf)
        ticket_id = cast(str, ticket["id"])
        version = _start_work(technician, technician_csrf, ticket_id)
        proposal = _propose(technician, technician_csrf, ticket_id, version).json()["data"]
        assert (
            approver.post(
                f"/api/v1/approval-requests/{proposal['id']}/decisions",
                headers=_headers(approver_csrf),
                json={"decision": "approve", "reason": "Concurrent execution test."},
            ).status_code
            == 200
        )

        def execute() -> int:
            with TestClient(automation_application) as concurrent_client:
                concurrent_csrf = _login(concurrent_client, "technician-one")
                return concurrent_client.post(
                    f"/api/v1/approval-requests/{proposal['id']}/executions",
                    headers=_headers(concurrent_csrf),
                ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(pool.map(lambda _: execute(), range(2)))

        assert statuses == [200, 409]

    database: Database = automation_application.state.database
    with database.create_session() as session:
        simulator = session.get(SimulatedVpnSessionRecord, "DEMO-VPN-001")
        assert simulator is not None
        assert simulator.reset_count == 1


def test_cancelled_ticket_invalidates_approved_proposal_without_side_effect(
    automation_application: FastAPI,
) -> None:
    with (
        TestClient(automation_application) as requester,
        TestClient(automation_application) as technician,
        TestClient(automation_application) as approver,
    ):
        requester_csrf = _login(requester, "requester-one")
        technician_csrf = _login(technician, "technician-one")
        approver_csrf = _login(approver, "approver-one")
        ticket = _create_ticket(requester, requester_csrf)
        ticket_id = cast(str, ticket["id"])
        version = _start_work(technician, technician_csrf, ticket_id)
        proposal = _propose(technician, technician_csrf, ticket_id, version).json()["data"]
        approved = approver.post(
            f"/api/v1/approval-requests/{proposal['id']}/decisions",
            headers=_headers(approver_csrf),
            json={"decision": "approve", "reason": "Synthetic evidence accepted."},
        )
        assert approved.status_code == 200

        cancelled = technician.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_headers(technician_csrf, **{"If-Match": f'"{version}"'}),
            json={"target": "cancelled", "reason": "Request withdrawn safely."},
        )
        assert cancelled.status_code == 200

        execution = technician.post(
            f"/api/v1/approval-requests/{proposal['id']}/executions",
            headers=_headers(technician_csrf),
        )
        simulator = technician.get("/api/v1/simulators/vpn/DEMO-VPN-001")
        assert execution.status_code in {409, 412}
        assert execution.json()["code"] in {"ACTION_CONFLICT", "VERSION_MISMATCH"}
        assert simulator.json()["data"]["reset_count"] == 0

    database: Database = automation_application.state.database
    with database.create_session() as session:
        assert session.scalar(select(func.count()).select_from(ActionExecutionRecord)) == 0
