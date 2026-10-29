"""Lexical knowledge retrieval, citations, abstention, and role boundaries."""

import json
from pathlib import Path
from typing import cast

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opsbridge.application.knowledge import CorpusManifest
from opsbridge.application.knowledge_evaluation import RetrievalDataset, evaluate_retrieval
from opsbridge.domain.tickets import ActorRole
from opsbridge.infrastructure.config import Settings
from opsbridge.presentation.http.app import create_app

BACKEND = Path(__file__).resolve().parents[1]
PASSWORD = "knowledge-test-password"  # noqa: S105
ORIGIN = "http://127.0.0.1:5173"


@pytest.fixture
def knowledge_client(tmp_path: Path) -> TestClient:
    database_path = tmp_path / "knowledge.db"
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path.as_posix()}")
    command.upgrade(config, "head")
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite+pysqlite:///{database_path.as_posix()}",
    )
    application = create_app(settings)
    manifest = CorpusManifest.model_validate(
        json.loads((BACKEND / "data" / "knowledge" / "corpus.json").read_text("utf-8"))
    )
    assert application.state.knowledge_service.ingest(manifest) == (4, 0)
    assert application.state.knowledge_service.ingest(manifest) == (0, 4)
    auth = application.state.auth_service
    for login, role in (
        ("kb.requester", ActorRole.REQUESTER),
        ("kb.technician", ActorRole.TECHNICIAN),
    ):
        auth.create_user(
            login_id=login,
            display_name=f"Synthetic {login}",
            role=role,
            password=PASSWORD,
        )
    return TestClient(application)


def _login(client: TestClient, login: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"login_id": login, "password": PASSWORD},
    )
    assert response.status_code == 204


def test_search_returns_real_citations_and_chunk_can_be_opened(
    knowledge_client: TestClient,
) -> None:
    _login(knowledge_client, "kb.requester")
    response = knowledge_client.get("/api/v1/knowledge/search?q=sesion%20VPN%20bloqueada")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "rag_lexical"
    assert body["abstained"] is False
    citation = body["citations"][0]
    assert citation["document_code"] == "KB-VPN-001"
    assert citation["chunk_id"] == "KB-VPN-001-C02"
    opened = knowledge_client.get(cast(str, citation["href"]))
    assert opened.status_code == 200
    assert opened.json()["content"] == citation["content"]
    assert response.headers["cache-control"] == "no-store"


def test_role_scope_and_abstention_do_not_leak_restricted_documents(
    knowledge_client: TestClient,
) -> None:
    _login(knowledge_client, "kb.requester")
    requester = knowledge_client.get("/api/v1/knowledge/search?q=diagnostico%20sinteticos")
    assert requester.status_code == 200
    assert requester.json()["abstained"] is True
    hidden = knowledge_client.get("/api/v1/knowledge/documents/KB-HW-001/chunks/KB-HW-001-C01")
    assert hidden.status_code == 404

    knowledge_client.cookies.clear()
    _login(knowledge_client, "kb.technician")
    technician = knowledge_client.get("/api/v1/knowledge/search?q=diagnostico%20sinteticos")
    assert technician.status_code == 200
    assert technician.json()["citations"][0]["document_code"] == "KB-HW-001"


def test_adversarial_content_is_returned_as_cited_data_not_an_instruction(
    knowledge_client: TestClient,
) -> None:
    _login(knowledge_client, "kb.technician")
    response = knowledge_client.get("/api/v1/knowledge/search?q=ignore%20politicas")
    assert response.status_code == 200
    body = response.json()
    assert body["citations"][0]["chunk_id"] == "KB-HW-001-C02"
    assert "contenido no confiable" in body["citations"][0]["content"].lower()


def test_search_requires_session_and_rejects_non_terms(knowledge_client: TestClient) -> None:
    assert knowledge_client.get("/api/v1/knowledge/search?q=vpn").status_code == 401
    _login(knowledge_client, "kb.requester")
    assert knowledge_client.get("/api/v1/knowledge/search?q=___").status_code == 400


def test_frozen_retrieval_dataset_has_reproducible_metrics(
    knowledge_client: TestClient,
) -> None:
    application = cast(FastAPI, knowledge_client.app)
    dataset = RetrievalDataset.model_validate(
        json.loads((BACKEND / "data" / "evaluation" / "retrieval_v1.json").read_text("utf-8"))
    )
    metrics = evaluate_retrieval(application.state.knowledge_service, dataset)
    assert metrics.cases == 13
    assert metrics.answerable_cases == 9
    assert metrics.expected_citations == 9
    assert metrics.recall_at_3 == 1.0
    assert metrics.precision_at_3 == 1.0
    assert metrics.abstention_accuracy == 1.0
