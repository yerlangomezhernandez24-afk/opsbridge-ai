"""FastAPI application factory and dependency composition root."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from opsbridge import __version__
from opsbridge.application.automation import AutomationService
from opsbridge.application.health import HealthService
from opsbridge.application.knowledge import KnowledgeService
from opsbridge.infrastructure.auth_composition import create_auth_service
from opsbridge.infrastructure.config import Settings, get_settings
from opsbridge.infrastructure.db import Database
from opsbridge.infrastructure.observability import configure_logging
from opsbridge.infrastructure.ticket_composition import create_ticket_service
from opsbridge.presentation.http.errors import register_exception_handlers
from opsbridge.presentation.http.middleware import CorrelationIdMiddleware
from opsbridge.presentation.http.routes.auth import create_auth_router
from opsbridge.presentation.http.routes.automation import create_automation_router
from opsbridge.presentation.http.routes.health import create_health_router
from opsbridge.presentation.http.routes.knowledge import create_knowledge_router
from opsbridge.presentation.http.routes.tickets import create_ticket_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Compose concrete adapters and return a testable FastAPI instance."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    database = Database(resolved_settings.database_url)
    health_service = HealthService(database_check=database.ping)
    auth_service = create_auth_service(database, resolved_settings)
    ticket_service = create_ticket_service(database)
    knowledge_service = KnowledgeService(database)
    automation_service = AutomationService(database)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        database.dispose()

    application = FastAPI(
        title="OpsBridge AI API",
        summary="Local-first IT operations backend",
        description=(
            "Authenticated local IT operations API with tickets and role-scoped lexical "
            "knowledge retrieval. Local LLM and automation modes are reported separately."
        ),
        version=__version__,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url=None,
        debug=False,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.database = database
    application.state.auth_service = auth_service
    application.state.ticket_service = ticket_service
    application.state.knowledge_service = knowledge_service
    application.state.automation_service = automation_service
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[resolved_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=[
            "Content-Type",
            "X-CSRF-Token",
            "X-Correlation-ID",
            "Idempotency-Key",
            "If-Match",
        ],
    )
    application.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(application)
    application.include_router(create_health_router(health_service))
    application.include_router(create_auth_router(auth_service, resolved_settings))
    application.include_router(
        create_ticket_router(ticket_service, auth_service, resolved_settings)
    )
    application.include_router(create_knowledge_router(knowledge_service, auth_service))
    application.include_router(
        create_automation_router(automation_service, auth_service, resolved_settings)
    )
    return application
