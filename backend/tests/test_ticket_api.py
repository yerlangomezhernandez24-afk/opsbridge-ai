"""Ticket REST API, resource authorization, ETag, and idempotency tests."""

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
from opsbridge.application.tickets import CreateTicketCommand, TicketService
from opsbridge.domain.tickets import (
    ActorRole,
    TicketCategory,
    TicketImpact,
    TicketUrgency,
    TicketValidationError,
)
from opsbridge.infrastructure.config import Settings
from opsbridge.infrastructure.db import Base, Database, TicketRecord
from opsbridge.presentation.http.app import create_app

ORIGIN = "http://127.0.0.1:5173"
PASSWORD = "ticket-api-test-password"  # noqa: S105
VPN_PAYLOAD = {
    "title": "Demo VPN connection fails",
    "description": "The synthetic VPN client reports DEMO-104 during connection.",
    "category": "network.vpn",
    "impact": "single_user",
    "urgency": "medium",
}


def _auth(application: FastAPI) -> AuthService:
    service: AuthService = application.state.auth_service
    return service


def _tickets(application: FastAPI) -> TicketService:
    service: TicketService = application.state.ticket_service
    return service


def _create_user(application: FastAPI, login: str, role: ActorRole) -> None:
    _auth(application).create_user(
        login_id=login,
        display_name=f"Synthetic {login}",
        role=role,
        password=PASSWORD,
    )


def _login(client: TestClient, login: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"login_id": login, "password": PASSWORD},
    )
    assert response.status_code == 204
    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200
    return cast(str, session.json()["csrf_token"])


def _mutation_headers(csrf: str, **extra: str) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": csrf, **extra}


def _create_ticket(client: TestClient, csrf: str, key: str | None = None) -> Response:
    return client.post(
        "/api/v1/tickets",
        headers=_mutation_headers(csrf, **{"Idempotency-Key": key or str(uuid4())}),
        json=VPN_PAYLOAD,
    )


@pytest.fixture
def ticket_application(test_settings: Settings) -> Iterator[FastAPI]:
    application = create_app(test_settings)
    Base.metadata.create_all(application.state.database.engine)
    yield application
    application.state.database.dispose()


def test_requester_creates_reads_lists_and_replays_ticket(
    ticket_application: FastAPI,
) -> None:
    _create_user(ticket_application, "requester-one", ActorRole.REQUESTER)
    key = str(uuid4())
    with TestClient(ticket_application) as client:
        csrf = _login(client, "requester-one")
        created = _create_ticket(client, csrf, key)
        replay = _create_ticket(client, csrf, key)

        assert created.status_code == replay.status_code == 201
        assert created.json()["data"] == replay.json()["data"]
        assert replay.headers["idempotency-replayed"] == "true"
        assert created.headers["etag"] == '"1"'
        ticket_id = created.json()["data"]["id"]
        detail = client.get(f"/api/v1/tickets/{ticket_id}")
        listing = client.get("/api/v1/tickets?page_size=25&category=network.vpn")
        timeline = client.get(f"/api/v1/tickets/{ticket_id}/timeline")

        assert detail.status_code == 200
        assert listing.status_code == 200
        assert [item["id"] for item in listing.json()["data"]] == [ticket_id]
        assert timeline.json()["data"][0]["type"] == "TicketCreated"
        assert len(timeline.json()["data"]) == 1

    database: Database = ticket_application.state.database
    with database.create_session() as session:
        assert session.scalar(select(func.count()).select_from(TicketRecord)) == 1


def test_idempotency_rejects_changed_payload_and_is_scoped_per_user(
    ticket_application: FastAPI,
) -> None:
    _create_user(ticket_application, "requester-one", ActorRole.REQUESTER)
    _create_user(ticket_application, "requester-two", ActorRole.REQUESTER)
    key = str(uuid4())
    with TestClient(ticket_application) as first, TestClient(ticket_application) as second:
        first_csrf = _login(first, "requester-one")
        second_csrf = _login(second, "requester-two")
        assert _create_ticket(first, first_csrf, key).status_code == 201
        changed = {
            **VPN_PAYLOAD,
            "description": "A different synthetic request with enough descriptive content.",
        }
        conflict = first.post(
            "/api/v1/tickets",
            headers=_mutation_headers(first_csrf, **{"Idempotency-Key": key}),
            json=changed,
        )
        other_user = _create_ticket(second, second_csrf, key)

        assert conflict.status_code == 409
        assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
        assert other_user.status_code == 201
        assert other_user.json()["data"]["id"] != conflict.json().get("id")


def test_requester_cannot_enumerate_or_modify_another_requesters_ticket(
    ticket_application: FastAPI,
) -> None:
    _create_user(ticket_application, "owner-user", ActorRole.REQUESTER)
    _create_user(ticket_application, "other-user", ActorRole.REQUESTER)
    with TestClient(ticket_application) as owner, TestClient(ticket_application) as other:
        owner_csrf = _login(owner, "owner-user")
        other_csrf = _login(other, "other-user")
        ticket_id = _create_ticket(owner, owner_csrf).json()["data"]["id"]

        hidden = other.get(f"/api/v1/tickets/{ticket_id}")
        listing = other.get("/api/v1/tickets")
        modified = other.patch(
            f"/api/v1/tickets/{ticket_id}",
            headers=_mutation_headers(other_csrf, **{"If-Match": '"1"'}),
            json={"category": "software.application"},
        )

        assert hidden.status_code == modified.status_code == 404
        assert hidden.json()["detail"] == modified.json()["detail"]
        assert listing.json()["data"] == []


def test_technician_transition_etag_and_stale_precondition(
    ticket_application: FastAPI,
) -> None:
    _create_user(ticket_application, "owner-user", ActorRole.REQUESTER)
    _create_user(ticket_application, "tech-user", ActorRole.TECHNICIAN)
    with TestClient(ticket_application) as owner, TestClient(ticket_application) as tech:
        owner_csrf = _login(owner, "owner-user")
        tech_csrf = _login(tech, "tech-user")
        ticket_id = _create_ticket(owner, owner_csrf).json()["data"]["id"]
        missing = tech.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(tech_csrf),
            json={"target": "triaged"},
        )
        triaged = tech.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(tech_csrf, **{"If-Match": '"1"'}),
            json={"target": "triaged"},
        )
        stale = tech.patch(
            f"/api/v1/tickets/{ticket_id}",
            headers=_mutation_headers(tech_csrf, **{"If-Match": '"1"'}),
            json={"impact": "multiple_users"},
        )

        assert missing.status_code == 428
        assert triaged.status_code == 200
        assert triaged.headers["etag"] == '"2"'
        assert stale.status_code == 412
        assert stale.json()["code"] == "VERSION_MISMATCH"
        final = tech.get(f"/api/v1/tickets/{ticket_id}").json()["data"]
        assert final["status"] == "triaged"
        assert final["impact"] == "single_user"
        timeline = tech.get(f"/api/v1/tickets/{ticket_id}/timeline").json()["data"]
        assert [event["revision"] for event in timeline] == [1, 2]


def test_mutations_require_authentication_origin_csrf_and_forbid_mass_assignment(
    ticket_application: FastAPI,
) -> None:
    _create_user(ticket_application, "requester-one", ActorRole.REQUESTER)
    with TestClient(ticket_application) as client:
        unauthenticated = client.post("/api/v1/tickets", json=VPN_PAYLOAD)
        csrf = _login(client, "requester-one")
        missing_csrf = client.post(
            "/api/v1/tickets",
            headers={"Origin": ORIGIN, "Idempotency-Key": str(uuid4())},
            json=VPN_PAYLOAD,
        )
        wrong_origin = client.post(
            "/api/v1/tickets",
            headers={
                "Origin": "http://localhost:5173",
                "X-CSRF-Token": csrf,
                "Idempotency-Key": str(uuid4()),
            },
            json=VPN_PAYLOAD,
        )
        escalation = client.post(
            "/api/v1/tickets",
            headers=_mutation_headers(csrf, **{"Idempotency-Key": str(uuid4())}),
            json={**VPN_PAYLOAD, "requester_id": str(uuid4()), "role": "technician"},
        )

        assert unauthenticated.status_code == 401
        assert missing_csrf.status_code == wrong_origin.status_code == 403
        assert escalation.status_code == 422

    database: Database = ticket_application.state.database
    with database.create_session() as session:
        assert session.scalar(select(func.count()).select_from(TicketRecord)) == 0


def test_pagination_cursor_and_filters_are_deterministic(
    ticket_application: FastAPI,
) -> None:
    _create_user(ticket_application, "requester-one", ActorRole.REQUESTER)
    with TestClient(ticket_application) as client:
        csrf = _login(client, "requester-one")
        ids = [_create_ticket(client, csrf).json()["data"]["id"] for _ in range(3)]
        first = client.get("/api/v1/tickets?page_size=2&status=new")
        cursor = first.json()["meta"]["next_cursor"]
        second = client.get(f"/api/v1/tickets?page_size=2&status=new&cursor={cursor}")

        returned = [item["id"] for item in first.json()["data"] + second.json()["data"]]
        assert first.json()["meta"]["has_more"] is True
        assert second.json()["meta"]["has_more"] is False
        assert set(returned) == set(ids)
        assert len(returned) == len(set(returned)) == 3


def test_summary_and_cursor_cover_more_than_one_hundred_scoped_tickets(
    ticket_application: FastAPI,
) -> None:
    owner = _auth(ticket_application).create_user(
        login_id="summary-owner",
        display_name="Summary Owner",
        role=ActorRole.REQUESTER,
        password=PASSWORD,
    )
    other = _auth(ticket_application).create_user(
        login_id="summary-other",
        display_name="Summary Other",
        role=ActorRole.REQUESTER,
        password=PASSWORD,
    )
    _create_user(ticket_application, "summary-tech", ActorRole.TECHNICIAN)
    service = _tickets(ticket_application)

    for index in range(105):
        service.create(
            user=owner,
            command=CreateTicketCommand(
                title=f"Owner synthetic ticket {index:03d}",
                description="Synthetic pagination evidence with no private operational data.",
                category=(
                    TicketCategory.NETWORK_VPN
                    if index % 2 == 0
                    else TicketCategory.SOFTWARE_APPLICATION
                ),
                impact=TicketImpact.SINGLE_USER,
                urgency=TicketUrgency.MEDIUM,
            ),
            idempotency_key=uuid4(),
        )
    for index in range(7):
        service.create(
            user=other,
            command=CreateTicketCommand(
                title=f"Other synthetic ticket {index:03d}",
                description="Synthetic role-scope evidence with no private operational data.",
                category=TicketCategory.HARDWARE_ENDPOINT,
                impact=TicketImpact.SINGLE_USER,
                urgency=TicketUrgency.LOW,
            ),
            idempotency_key=uuid4(),
        )

    with (
        TestClient(ticket_application) as owner_client,
        TestClient(ticket_application) as other_client,
        TestClient(ticket_application) as tech_client,
    ):
        _login(owner_client, "summary-owner")
        _login(other_client, "summary-other")
        _login(tech_client, "summary-tech")

        first = owner_client.get("/api/v1/tickets?page_size=100")
        cursor = first.json()["meta"]["next_cursor"]
        second = owner_client.get(f"/api/v1/tickets?page_size=100&cursor={cursor}")
        owner_summary = owner_client.get("/api/v1/tickets/summary")
        filtered = owner_client.get("/api/v1/tickets/summary?category=network.vpn")
        multi_filtered = owner_client.get(
            "/api/v1/tickets/summary?status=new&priority=p3&query=ticket%2000"
        )
        other_summary = other_client.get("/api/v1/tickets/summary")
        tech_summary = tech_client.get("/api/v1/tickets/summary")

        assert first.status_code == second.status_code == 200
        assert len(first.json()["data"]) == 100
        assert first.json()["meta"]["has_more"] is True
        assert len(second.json()["data"]) == 5
        assert second.json()["meta"]["has_more"] is False
        assert owner_summary.json()["data"]["total"] == 105
        assert filtered.json()["data"]["total"] == 53
        assert multi_filtered.json()["data"]["total"] == 10
        assert other_summary.json()["data"]["total"] == 7
        assert tech_summary.json()["data"]["total"] == 112
        assert sum(item["value"] for item in tech_summary.json()["data"]["by_status"]) == 112


def test_concurrent_identical_creations_return_one_ticket(
    ticket_application: FastAPI,
) -> None:
    _create_user(ticket_application, "concurrent-user", ActorRole.REQUESTER)
    key = str(uuid4())
    login_result = _auth(ticket_application).login(
        login_id="concurrent-user", password=PASSWORD, existing_session_token=None
    )

    def submit() -> tuple[int, str]:
        with TestClient(ticket_application) as client:
            client.cookies.set("opsbridge_session", login_result.session_token)
            response = _create_ticket(client, login_result.state.csrf_token, key)
            return response.status_code, cast(str, response.json()["data"]["id"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: submit(), range(2)))

    assert [status for status, _ in results] == [201, 201]
    assert len({ticket_id for _, ticket_id in results}) == 1
    database: Database = ticket_application.state.database
    with database.create_session() as session:
        assert session.scalar(select(func.count()).select_from(TicketRecord)) == 1


def test_idempotency_survives_application_restart(test_settings: Settings) -> None:
    first_app = create_app(test_settings)
    Base.metadata.create_all(first_app.state.database.engine)
    _create_user(first_app, "restart-user", ActorRole.REQUESTER)
    key = str(uuid4())
    with TestClient(first_app) as first:
        csrf = _login(first, "restart-user")
        created = _create_ticket(first, csrf, key)
        token = first.cookies.get("opsbridge_session")
    assert token is not None

    second_app = create_app(test_settings)
    with TestClient(second_app) as second:
        second.cookies.set("opsbridge_session", token)
        state = second.get("/api/v1/auth/session")
        replay = _create_ticket(second, state.json()["csrf_token"], key)
        assert replay.status_code == 201
        assert replay.headers["idempotency-replayed"] == "true"
        assert replay.json()["data"]["id"] == created.json()["data"]["id"]


def test_failed_creation_rolls_back_idempotency_and_can_retry(
    ticket_application: FastAPI,
) -> None:
    user = _auth(ticket_application).create_user(
        login_id="rollback-user",
        display_name="Rollback User",
        role=ActorRole.REQUESTER,
        password=PASSWORD,
    )
    key = uuid4()
    with pytest.raises(TicketValidationError):
        _tickets(ticket_application).create(
            user=user,
            command=CreateTicketCommand(
                title="bad",
                description=VPN_PAYLOAD["description"],
                category=TicketCategory.NETWORK_VPN,
                impact=TicketImpact.SINGLE_USER,
                urgency=TicketUrgency.MEDIUM,
            ),
            idempotency_key=key,
        )
    result = _tickets(ticket_application).create(
        user=user,
        command=CreateTicketCommand(
            title=VPN_PAYLOAD["title"],
            description=VPN_PAYLOAD["description"],
            category=TicketCategory.NETWORK_VPN,
            impact=TicketImpact.SINGLE_USER,
            urgency=TicketUrgency.MEDIUM,
        ),
        idempotency_key=key,
    )
    assert result.replayed is False


def test_technician_cannot_modify_ticket_assigned_to_another_technician(
    ticket_application: FastAPI,
) -> None:
    _create_user(ticket_application, "owner-user", ActorRole.REQUESTER)
    _create_user(ticket_application, "tech-one", ActorRole.TECHNICIAN)
    _create_user(ticket_application, "tech-two", ActorRole.TECHNICIAN)
    with (
        TestClient(ticket_application) as owner,
        TestClient(ticket_application) as first,
        TestClient(ticket_application) as second,
    ):
        owner_csrf = _login(owner, "owner-user")
        first_csrf = _login(first, "tech-one")
        second_csrf = _login(second, "tech-two")
        ticket_id = _create_ticket(owner, owner_csrf).json()["data"]["id"]
        triaged = first.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(first_csrf, **{"If-Match": '"1"'}),
            json={"target": "triaged"},
        )
        assigned = first.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(first_csrf, **{"If-Match": triaged.headers["etag"]}),
            json={"target": "in_progress"},
        )
        rejected = second.patch(
            f"/api/v1/tickets/{ticket_id}",
            headers=_mutation_headers(second_csrf, **{"If-Match": assigned.headers["etag"]}),
            json={"category": "software.application"},
        )
        assert assigned.status_code == 200
        assert rejected.status_code == 403
        assert (
            second.get(f"/api/v1/tickets/{ticket_id}").json()["data"]["category"] == "network.vpn"
        )


def test_invalid_transition_and_malformed_etag_do_not_change_ticket(
    ticket_application: FastAPI,
) -> None:
    _create_user(ticket_application, "owner-user", ActorRole.REQUESTER)
    _create_user(ticket_application, "tech-user", ActorRole.TECHNICIAN)
    with TestClient(ticket_application) as owner, TestClient(ticket_application) as tech:
        owner_csrf = _login(owner, "owner-user")
        tech_csrf = _login(tech, "tech-user")
        ticket_id = _create_ticket(owner, owner_csrf).json()["data"]["id"]
        malformed = tech.patch(
            f"/api/v1/tickets/{ticket_id}",
            headers=_mutation_headers(tech_csrf, **{"If-Match": "1"}),
            json={"category": "software.application"},
        )
        invalid = tech.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(tech_csrf, **{"If-Match": '"1"'}),
            json={"target": "resolved", "resolution_summary": "Cannot skip states"},
        )
        final = tech.get(f"/api/v1/tickets/{ticket_id}")

        assert malformed.status_code == 400
        assert invalid.status_code == 409
        assert final.json()["data"]["version"] == 1


def test_transition_options_drive_complete_authorized_ticket_cycle(
    ticket_application: FastAPI,
) -> None:
    _create_user(ticket_application, "cycle-owner", ActorRole.REQUESTER)
    _create_user(ticket_application, "cycle-tech", ActorRole.TECHNICIAN)
    with TestClient(ticket_application) as owner, TestClient(ticket_application) as tech:
        owner_csrf = _login(owner, "cycle-owner")
        tech_csrf = _login(tech, "cycle-tech")
        created = _create_ticket(owner, owner_csrf)
        ticket_id = created.json()["data"]["id"]

        owner_options = owner.get(f"/api/v1/tickets/{ticket_id}/transition-options")
        tech_options = tech.get(f"/api/v1/tickets/{ticket_id}/transition-options")
        assert owner_options.json()["data"] == [{"target": "cancelled", "required_fields": []}]
        assert {item["target"] for item in tech_options.json()["data"]} == {
            "triaged",
            "cancelled",
        }

        triaged = tech.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(tech_csrf, **{"If-Match": created.headers["etag"]}),
            json={"target": "triaged"},
        )
        started = tech.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(tech_csrf, **{"If-Match": triaged.headers["etag"]}),
            json={"target": "in_progress"},
        )
        in_progress_options = tech.get(f"/api/v1/tickets/{ticket_id}/transition-options").json()[
            "data"
        ]
        assert {item["target"] for item in in_progress_options} == {
            "waiting_requester",
            "resolved",
            "cancelled",
        }
        assert "waiting_approval" not in {item["target"] for item in in_progress_options}

        resolved = tech.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(tech_csrf, **{"If-Match": started.headers["etag"]}),
            json={
                "target": "resolved",
                "resolution_summary": "Synthetic VPN recovery verified by the technician.",
            },
        )
        owner_close_options = owner.get(f"/api/v1/tickets/{ticket_id}/transition-options")
        closed = owner.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(owner_csrf, **{"If-Match": resolved.headers["etag"]}),
            json={"target": "closed", "requester_confirmed": True},
        )

        assert triaged.status_code == started.status_code == resolved.status_code == 200
        assert owner_close_options.json()["data"] == [
            {"target": "closed", "required_fields": ["requester_confirmed"]}
        ]
        assert closed.status_code == 200
        assert closed.json()["data"]["status"] == "closed"
        assert closed.json()["data"]["resolution_summary"].startswith("Synthetic VPN")


def test_client_approval_claims_are_rejected_without_changing_ticket(
    ticket_application: FastAPI,
) -> None:
    _create_user(ticket_application, "approval-owner", ActorRole.REQUESTER)
    _create_user(ticket_application, "approval-tech", ActorRole.TECHNICIAN)
    with TestClient(ticket_application) as owner, TestClient(ticket_application) as tech:
        owner_csrf = _login(owner, "approval-owner")
        tech_csrf = _login(tech, "approval-tech")
        created = _create_ticket(owner, owner_csrf)
        ticket_id = created.json()["data"]["id"]
        triaged = tech.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(tech_csrf, **{"If-Match": created.headers["etag"]}),
            json={"target": "triaged"},
        )
        started = tech.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(tech_csrf, **{"If-Match": triaged.headers["etag"]}),
            json={"target": "in_progress"},
        )

        forged_flag = tech.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(tech_csrf, **{"If-Match": started.headers["etag"]}),
            json={"target": "waiting_approval", "approval_resolved": True},
        )
        forged_reference = tech.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(tech_csrf, **{"If-Match": started.headers["etag"]}),
            json={"target": "waiting_approval", "approval_reference": "invented"},
        )
        unsupported = tech.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(tech_csrf, **{"If-Match": started.headers["etag"]}),
            json={"target": "waiting_approval"},
        )
        final = tech.get(f"/api/v1/tickets/{ticket_id}")
        timeline = tech.get(f"/api/v1/tickets/{ticket_id}/timeline")

        assert forged_flag.status_code == forged_reference.status_code == 422
        assert unsupported.status_code == 403
        assert final.json()["data"]["status"] == "in_progress"
        assert final.json()["data"]["version"] == 3
        assert max(event["revision"] for event in timeline.json()["data"]) == 3


def test_two_concurrent_http_updates_from_same_etag_have_one_winner(
    ticket_application: FastAPI,
) -> None:
    _create_user(ticket_application, "tech-user", ActorRole.TECHNICIAN)
    with TestClient(ticket_application) as creator:
        csrf = _login(creator, "tech-user")
        created = _create_ticket(creator, csrf)
        ticket_id = created.json()["data"]["id"]
        token = creator.cookies.get("opsbridge_session")
    assert token is not None

    def update_ticket(category: str) -> int:
        with TestClient(ticket_application) as client:
            client.cookies.set("opsbridge_session", token)
            state = client.get("/api/v1/auth/session").json()
            response = client.patch(
                f"/api/v1/tickets/{ticket_id}",
                headers=_mutation_headers(
                    state["csrf_token"], **{"If-Match": created.headers["etag"]}
                ),
                json={"category": category},
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(update_ticket, ["software.application", "hardware.endpoint"]))
    assert sorted(statuses) == [200, 412]


def test_reproducible_vpn_business_scenario(ticket_application: FastAPI) -> None:
    """Exercise the reviewed requester -> technician flow only through real HTTP."""

    _create_user(ticket_application, "vpn-requester", ActorRole.REQUESTER)
    _create_user(ticket_application, "vpn-technician", ActorRole.TECHNICIAN)
    _create_user(ticket_application, "unrelated-requester", ActorRole.REQUESTER)
    key = str(uuid4())
    with (
        TestClient(ticket_application) as requester,
        TestClient(ticket_application) as technician,
        TestClient(ticket_application) as unrelated,
    ):
        requester_csrf = _login(requester, "vpn-requester")
        technician_csrf = _login(technician, "vpn-technician")
        _login(unrelated, "unrelated-requester")
        created = _create_ticket(requester, requester_csrf, key)
        ticket_id = created.json()["data"]["id"]

        assert created.json()["data"]["key"].startswith("OPS-")
        assert technician.get(f"/api/v1/tickets/{ticket_id}").status_code == 200
        triaged = technician.post(
            f"/api/v1/tickets/{ticket_id}/transitions",
            headers=_mutation_headers(technician_csrf, **{"If-Match": created.headers["etag"]}),
            json={"target": "triaged"},
        )
        stale = technician.patch(
            f"/api/v1/tickets/{ticket_id}",
            headers=_mutation_headers(technician_csrf, **{"If-Match": created.headers["etag"]}),
            json={"category": "software.application"},
        )
        hidden = unrelated.get(f"/api/v1/tickets/{ticket_id}")
        replay = _create_ticket(requester, requester_csrf, key)
        timeline = requester.get(f"/api/v1/tickets/{ticket_id}/timeline")

        assert triaged.status_code == 200
        assert stale.status_code == 412
        assert hidden.status_code == 404
        assert replay.headers["idempotency-replayed"] == "true"
        assert replay.json()["data"]["id"] == ticket_id
        assert replay.json()["data"]["status"] == "new"
        assert replay.json()["data"]["version"] == 1
        assert [event["revision"] for event in timeline.json()["data"]] == [1, 2]
        assert timeline.headers["etag"] == triaged.headers["etag"]


def test_approver_has_read_access_but_no_ticket_mutation_authority(
    ticket_application: FastAPI,
) -> None:
    _create_user(ticket_application, "owner-user", ActorRole.REQUESTER)
    _create_user(ticket_application, "approver-user", ActorRole.APPROVER)
    with TestClient(ticket_application) as owner, TestClient(ticket_application) as approver:
        owner_csrf = _login(owner, "owner-user")
        approver_csrf = _login(approver, "approver-user")
        created = _create_ticket(owner, owner_csrf)
        ticket_id = created.json()["data"]["id"]

        assert approver.get(f"/api/v1/tickets/{ticket_id}").status_code == 200
        denied_create = _create_ticket(approver, approver_csrf)
        denied_patch = approver.patch(
            f"/api/v1/tickets/{ticket_id}",
            headers=_mutation_headers(approver_csrf, **{"If-Match": created.headers["etag"]}),
            json={"category": "software.application"},
        )
        assert denied_create.status_code == denied_patch.status_code == 403


def test_malformed_identifiers_filters_cursor_and_idempotency_key_are_controlled(
    ticket_application: FastAPI,
) -> None:
    _create_user(ticket_application, "requester-one", ActorRole.REQUESTER)
    with TestClient(ticket_application) as client:
        csrf = _login(client, "requester-one")
        assert client.get("/api/v1/tickets/not-a-uuid").status_code == 404
        assert client.get("/api/v1/tickets?status=unknown").status_code == 400
        assert client.get("/api/v1/tickets?cursor=not-base64!").status_code == 400
        invalid_key = client.post(
            "/api/v1/tickets",
            headers=_mutation_headers(csrf, **{"Idempotency-Key": "not-a-uuid"}),
            json=VPN_PAYLOAD,
        )
        missing_key = client.post(
            "/api/v1/tickets",
            headers=_mutation_headers(csrf),
            json=VPN_PAYLOAD,
        )
        assert invalid_key.status_code == missing_key.status_code == 400
