"""Safe RFC 9457-style problem responses for the HTTP boundary."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from opsbridge.application.errors import ApplicationError
from opsbridge.domain.tickets import (
    InvalidTransitionError,
    TicketDomainError,
    TransitionPreconditionError,
    UnauthorizedDomainOperationError,
)
from opsbridge.infrastructure.db.errors import (
    DatabaseLockedError,
    PersistenceError,
    TicketNotFoundError,
    TicketVersionConflictError,
)

logger = logging.getLogger(__name__)


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", "unavailable"))


def _problem(
    request: Request,
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    errors: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response_headers = {"Cache-Control": "no-store", **(headers or {})}
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": f"https://opsbridge.local/problems/{code.lower().replace('_', '-')}",
            "title": title,
            "status": status,
            "code": code,
            "detail": detail,
            "instance": request.url.path,
            "correlation_id": _correlation_id(request),
            "errors": errors or [],
        },
        headers=response_headers,
    )


def register_exception_handlers(application: FastAPI) -> None:
    """Install handlers that never return traces or exception strings."""

    @application.exception_handler(ApplicationError)
    async def application_error_handler(request: Request, exc: ApplicationError) -> JSONResponse:
        return _problem(
            request,
            status=exc.status_code,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
            headers=exc.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [{"location": list(error["loc"]), "type": error["type"]} for error in exc.errors()]
        if any(error["type"] == "json_invalid" for error in exc.errors()):
            return _problem(
                request,
                status=400,
                code="MALFORMED_REQUEST",
                title="Malformed request",
                detail="The JSON request body is invalid.",
                errors=errors,
            )
        return _problem(
            request,
            status=422,
            code="VALIDATION_ERROR",
            title="Validation error",
            detail="The request did not satisfy the API contract.",
            errors=errors,
        )

    @application.exception_handler(UnauthorizedDomainOperationError)
    async def unauthorized_domain_handler(
        request: Request, _: UnauthorizedDomainOperationError
    ) -> JSONResponse:
        return _problem(
            request,
            status=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="The operation is not permitted.",
        )

    @application.exception_handler(InvalidTransitionError)
    @application.exception_handler(TransitionPreconditionError)
    async def ticket_conflict_handler(request: Request, _: TicketDomainError) -> JSONResponse:
        return _problem(
            request,
            status=409,
            code="INVALID_TRANSITION",
            title="Ticket conflict",
            detail="The requested transition conflicts with the ticket state.",
        )

    @application.exception_handler(TicketDomainError)
    async def ticket_validation_handler(request: Request, _: TicketDomainError) -> JSONResponse:
        return _problem(
            request,
            status=422,
            code="VALIDATION_ERROR",
            title="Validation error",
            detail="The ticket operation violates the domain contract.",
        )

    @application.exception_handler(TicketVersionConflictError)
    async def version_conflict_handler(
        request: Request, _: TicketVersionConflictError
    ) -> JSONResponse:
        return _problem(
            request,
            status=412,
            code="VERSION_MISMATCH",
            title="Precondition failed",
            detail="The ticket version changed before the operation could commit.",
        )

    @application.exception_handler(TicketNotFoundError)
    async def ticket_not_found_handler(request: Request, _: TicketNotFoundError) -> JSONResponse:
        return _problem(
            request,
            status=404,
            code="RESOURCE_NOT_FOUND",
            title="Resource not found",
            detail="The requested resource is unavailable.",
        )

    @application.exception_handler(DatabaseLockedError)
    async def database_locked_handler(request: Request, _: DatabaseLockedError) -> JSONResponse:
        return _problem(
            request,
            status=503,
            code="STORAGE_TEMPORARILY_UNAVAILABLE",
            title="Storage unavailable",
            detail="Local storage is temporarily unavailable.",
            headers={"Retry-After": "1"},
        )

    @application.exception_handler(PersistenceError)
    async def persistence_error_handler(request: Request, _: PersistenceError) -> JSONResponse:
        return _problem(
            request,
            status=503,
            code="STORAGE_UNAVAILABLE",
            title="Storage unavailable",
            detail="Local storage could not complete the operation.",
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = "Resource not found" if exc.status_code == 404 else "HTTP error"
        code = "RESOURCE_NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return _problem(
            request,
            status=exc.status_code,
            code=code,
            title=title,
            detail="The requested resource is unavailable.",
        )

    @application.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, _: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_request_error",
            extra={
                "event": "unhandled_request_error",
                "correlation_id": _correlation_id(request),
                "method": request.method,
                "path": request.url.path,
            },
        )
        return _problem(
            request,
            status=500,
            code="INTERNAL_SERVER_ERROR",
            title="Internal server error",
            detail="The server could not complete the request.",
        )
