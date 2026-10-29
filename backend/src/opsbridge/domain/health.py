"""Health values shared without coupling the domain to HTTP or SQLAlchemy."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Immutable result returned by a health use case."""

    status: Literal["ok", "ready"]
    checks: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
