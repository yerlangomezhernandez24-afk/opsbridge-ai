"""Request correlation and minimal access logging."""

import logging
import time
from uuid import UUID, uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Use a valid client UUID or generate one, without logging query/body data."""

    @staticmethod
    def _resolve_correlation_id(raw_value: str | None) -> str:
        if raw_value is None:
            return str(uuid4())
        try:
            return str(UUID(raw_value))
        except ValueError:
            return str(uuid4())

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = self._resolve_correlation_id(request.headers.get("X-Correlation-ID"))
        request.state.correlation_id = correlation_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "request_completed",
            extra={
                "event": "request_completed",
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
