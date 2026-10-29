"""Bootstrap acceptance tests for package, factory, OpenAPI, and health."""

from uuid import UUID

from fastapi.testclient import TestClient

import opsbridge
from opsbridge.infrastructure.config import Settings
from opsbridge.presentation.http.app import create_app


def test_package_import() -> None:
    assert opsbridge.__version__ == "1.0.0rc1"


def test_application_factory(test_settings: Settings) -> None:
    application = create_app(test_settings)

    assert application.title == "OpsBridge AI API"
    assert application.version == opsbridge.__version__
    assert application.openapi_url == "/openapi.json"
    assert application.docs_url == "/docs"
    assert application.debug is False


def test_live_health(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "opsbridge-api"}
    UUID(response.headers["X-Correlation-ID"])


def test_ready_health_checks_database(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}


def test_openapi_contains_reviewed_local_api_routes(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert set(response.json()["paths"]) == {
        "/health/live",
        "/health/ready",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/session",
        "/api/v1/tickets",
        "/api/v1/tickets/summary",
        "/api/v1/tickets/{ticket_id}",
        "/api/v1/tickets/{ticket_id}/transitions",
        "/api/v1/tickets/{ticket_id}/transition-options",
        "/api/v1/tickets/{ticket_id}/timeline",
        "/api/v1/knowledge/search",
        "/api/v1/knowledge/documents/{document_code}/chunks/{chunk_id}",
        "/api/v1/tickets/{ticket_id}/action-proposals",
        "/api/v1/approval-requests",
        "/api/v1/approval-requests/{proposal_id}/decisions",
        "/api/v1/approval-requests/{proposal_id}/executions",
        "/api/v1/simulators/vpn/{identity_code}",
        "/api/v1/ai/status",
    }
