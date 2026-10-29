"""End-to-end local authentication boundary tests."""

from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select, update

from opsbridge.application.auth import AuthService
from opsbridge.domain.tickets import ActorRole
from opsbridge.infrastructure.db import AuthSessionRecord, UserRecord

ORIGIN = "http://127.0.0.1:5173"
PASSWORD = "correct horse battery staple"  # noqa: S105 - synthetic test secret


def _service(client: TestClient) -> AuthService:
    service: AuthService = cast(FastAPI, client.app).state.auth_service
    return service


def _create_user(client: TestClient, login: str = "alice") -> None:
    _service(client).create_user(
        login_id=login,
        display_name="Alice Requester",
        role=ActorRole.REQUESTER,
        password=PASSWORD,
    )


def _login(client: TestClient, *, login: str = "alice", password: str = PASSWORD) -> Response:
    return client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"login_id": login, "password": password},
    )


def test_login_session_logout_and_cookie_security(client: TestClient) -> None:
    _create_user(client)
    login = _login(client)

    assert login.status_code == 204
    cookie = login.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "correct horse" not in cookie
    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200
    body = session.json()
    assert body["login_id"] == "alice"
    assert body["role"] == "requester"
    assert body["csrf_token"] not in cookie
    assert session.headers["cache-control"] == "no-store"

    logout = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": body["csrf_token"]},
    )
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/session").status_code == 401


def test_login_requires_exact_origin_and_uses_generic_credentials_error(
    client: TestClient,
) -> None:
    _create_user(client)
    disallowed = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "http://localhost:5173"},
        json={"login_id": "alice", "password": PASSWORD},
    )
    missing = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"login_id": "missing", "password": PASSWORD},
    )
    wrong = _login(client, password="not the real password")  # noqa: S106

    assert disallowed.status_code == 403
    assert missing.status_code == wrong.status_code == 401
    assert missing.json()["detail"] == wrong.json()["detail"]


def test_logout_requires_csrf_and_does_not_revoke_on_rejection(client: TestClient) -> None:
    _create_user(client)
    assert _login(client).status_code == 204

    rejected = client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN})
    assert rejected.status_code == 403
    assert client.get("/api/v1/auth/session").status_code == 200


def test_login_rotates_existing_session_and_stores_only_verifier(client: TestClient) -> None:
    _create_user(client)
    assert _login(client).status_code == 204
    original = client.cookies.get("opsbridge_session")
    assert original is not None
    assert _login(client).status_code == 204
    replacement = client.cookies.get("opsbridge_session")
    assert replacement is not None and replacement != original

    database = cast(FastAPI, client.app).state.database
    with database.create_session() as session:
        records = list(session.scalars(select(AuthSessionRecord)))
    assert len(records) == 2
    assert records[0].revoked_at is not None
    assert all(record.token_hash not in {original, replacement} for record in records)


def test_disabled_user_session_is_revoked(client: TestClient) -> None:
    _create_user(client)
    assert _login(client).status_code == 204
    database = cast(FastAPI, client.app).state.database
    with database.session() as session:
        session.execute(update(UserRecord).values(is_active=False))

    assert client.get("/api/v1/auth/session").status_code == 401


def test_repeated_failures_are_rate_limited(client: TestClient) -> None:
    for _ in range(5):
        assert (
            _login(client, login="bruteforce", password="wrong password").status_code  # noqa: S106
            == 401
        )
    response = _login(client, login="bruteforce", password="wrong password")  # noqa: S106
    assert response.status_code == 429
    assert response.json()["code"] == "TOO_MANY_ATTEMPTS"
    assert response.headers["retry-after"] == "300"


def test_unauthenticated_session_is_safe_problem(client: TestClient) -> None:
    response = client.get("/api/v1/auth/session")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "traceback" not in response.text.lower()
