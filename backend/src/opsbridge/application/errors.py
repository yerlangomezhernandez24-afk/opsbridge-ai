"""Errors that presentation adapters translate into safe responses."""

from typing import ClassVar


class ApplicationError(Exception):
    """Base error with a stable public code and no internal details."""

    status_code = 500
    code = "APPLICATION_ERROR"
    title = "Application error"
    detail = "The request could not be completed."
    headers: ClassVar[dict[str, str]] = {}


class DependencyUnavailableError(ApplicationError):
    """Raised when a required local dependency does not respond."""

    status_code = 503
    code = "DEPENDENCY_UNAVAILABLE"
    title = "Dependency unavailable"
    detail = "A required local dependency is unavailable."


class InvalidCredentialsError(ApplicationError):
    status_code = 401
    code = "AUTHENTICATION_FAILED"
    title = "Authentication failed"
    detail = "The supplied credentials are invalid."


class AuthenticationRequiredError(ApplicationError):
    status_code = 401
    code = "AUTH_REQUIRED"
    title = "Authentication required"
    detail = "A valid session is required."


class SessionExpiredError(ApplicationError):
    status_code = 401
    code = "SESSION_EXPIRED"
    title = "Session expired"
    detail = "The session is no longer valid."


class ForbiddenError(ApplicationError):
    status_code = 403
    code = "FORBIDDEN"
    title = "Forbidden"
    detail = "The operation is not permitted."


class CsrfInvalidError(ApplicationError):
    status_code = 403
    code = "CSRF_INVALID"
    title = "CSRF validation failed"
    detail = "The request failed CSRF validation."


class OriginNotAllowedError(ApplicationError):
    status_code = 403
    code = "ORIGIN_NOT_ALLOWED"
    title = "Origin not allowed"
    detail = "The request origin is not allowed."


class TooManyLoginAttemptsError(ApplicationError):
    status_code = 429
    code = "TOO_MANY_ATTEMPTS"
    title = "Too many attempts"
    detail = "Too many authentication attempts were received. Try again later."
    headers: ClassVar[dict[str, str]] = {"Retry-After": "300"}


class DuplicateIdentityError(ApplicationError):
    status_code = 409
    code = "IDENTITY_CONFLICT"
    title = "Identity conflict"
    detail = "The local identity could not be created."


class PasswordPolicyError(ApplicationError):
    status_code = 422
    code = "PASSWORD_POLICY"
    title = "Password policy violation"
    detail = "The password does not satisfy the local policy."


class ResourceNotFoundError(ApplicationError):
    status_code = 404
    code = "RESOURCE_NOT_FOUND"
    title = "Resource not found"
    detail = "The requested resource is unavailable."


class IdempotencyConflictError(ApplicationError):
    status_code = 409
    code = "IDEMPOTENCY_CONFLICT"
    title = "Idempotency conflict"
    detail = "The idempotency key was already used for a different request."


class VersionMismatchError(ApplicationError):
    status_code = 412
    code = "VERSION_MISMATCH"
    title = "Precondition failed"
    detail = "The ticket version no longer matches the supplied precondition."


class PreconditionRequiredError(ApplicationError):
    status_code = 428
    code = "PRECONDITION_REQUIRED"
    title = "Precondition required"
    detail = "A valid If-Match header is required."


class MalformedRequestError(ApplicationError):
    status_code = 400
    code = "MALFORMED_REQUEST"
    title = "Malformed request"
    detail = "The request format is invalid."


class TicketConflictError(ApplicationError):
    status_code = 409
    code = "INVALID_TRANSITION"
    title = "Ticket conflict"
    detail = "The requested ticket operation conflicts with its current state."


class ToolNotAllowedError(ApplicationError):
    status_code = 422
    code = "TOOL_NOT_ALLOWED"
    title = "Tool not allowed"
    detail = "The requested tool or arguments are not in the local allowlist."


class SeparationOfDutiesError(ApplicationError):
    status_code = 403
    code = "SEPARATION_OF_DUTIES"
    title = "Separation of duties required"
    detail = "A different authorized user must approve this action."


class ActionConflictError(ApplicationError):
    status_code = 409
    code = "ACTION_CONFLICT"
    title = "Action conflict"
    detail = "The action is expired, stale, rejected, or already consumed."
