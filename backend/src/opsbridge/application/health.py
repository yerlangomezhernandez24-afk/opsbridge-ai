"""Health use cases."""

from collections.abc import Callable

from opsbridge.application.errors import DependencyUnavailableError
from opsbridge.domain.health import HealthReport


class HealthService:
    """Reports liveness and verifies the configured database connection."""

    def __init__(self, database_check: Callable[[], None]) -> None:
        self._database_check = database_check

    @staticmethod
    def liveness() -> HealthReport:
        return HealthReport(status="ok")

    def readiness(self) -> HealthReport:
        try:
            self._database_check()
        except Exception as exc:
            raise DependencyUnavailableError from exc
        return HealthReport(status="ready", checks={"database": "ok"})
