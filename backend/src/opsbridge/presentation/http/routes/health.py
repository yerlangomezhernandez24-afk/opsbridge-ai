"""Minimal liveness and readiness routes defined by the API design."""

from typing import Literal, cast

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from opsbridge.application.health import HealthService


class LiveHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    service: Literal["opsbridge-api"] = "opsbridge-api"


class ReadyHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready"]
    checks: dict[str, Literal["ok"]] = Field(min_length=1)


def create_health_router(service: HealthService) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health/live", response_model=LiveHealthResponse)
    async def live() -> LiveHealthResponse:
        report = service.liveness()
        return LiveHealthResponse(status=cast(Literal["ok"], report.status))

    @router.get("/health/ready", response_model=ReadyHealthResponse)
    async def ready() -> ReadyHealthResponse:
        report = service.readiness()
        return ReadyHealthResponse(
            status=cast(Literal["ready"], report.status),
            checks=cast(dict[str, Literal["ok"]], dict(report.checks)),
        )

    return router
