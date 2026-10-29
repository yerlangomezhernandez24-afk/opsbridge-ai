"""Minimal local authentication HTTP contract."""

from datetime import datetime

from fastapi import APIRouter, Cookie, Header, Response, status
from pydantic import BaseModel, ConfigDict, Field

from opsbridge.application.auth import AuthService, SessionState
from opsbridge.application.errors import (
    AuthenticationRequiredError,
    CsrfInvalidError,
    OriginNotAllowedError,
)
from opsbridge.infrastructure.config import Settings

SESSION_COOKIE = "opsbridge_session"


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login_id: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)


class SessionResponse(BaseModel):
    user_id: str
    login_id: str
    display_name: str
    role: str
    permissions: list[str]
    csrf_token: str
    expires_at: datetime


def create_auth_router(service: AuthService, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

    def require_origin(origin: str | None) -> None:
        if origin != settings.frontend_origin:
            raise OriginNotAllowedError

    @router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
    def login(
        payload: LoginRequest,
        response: Response,
        origin: str | None = Header(default=None),
        existing_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> None:
        require_origin(origin)
        result = service.login(
            login_id=payload.login_id,
            password=payload.password,
            existing_session_token=existing_session,
        )
        response.set_cookie(
            key=SESSION_COOKIE,
            value=result.session_token,
            max_age=settings.session_absolute_minutes * 60,
            path="/",
            secure=settings.session_cookie_secure,
            httponly=True,
            samesite="lax",
        )
        response.headers["Cache-Control"] = "no-store"

    @router.get("/session", response_model=SessionResponse)
    def read_session(
        response: Response,
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> SessionResponse:
        if not session_token:
            raise AuthenticationRequiredError
        state = service.session(session_token)
        response.headers["Cache-Control"] = "no-store"
        return _response(state)

    @router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
    def logout(
        response: Response,
        origin: str | None = Header(default=None),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> None:
        require_origin(origin)
        if not session_token:
            raise AuthenticationRequiredError
        if csrf_token is None or not service.csrf_matches(session_token, csrf_token):
            raise CsrfInvalidError
        service.logout(session_token)
        response.delete_cookie(
            key=SESSION_COOKIE,
            path="/",
            secure=settings.session_cookie_secure,
            httponly=True,
            samesite="lax",
        )
        response.headers["Cache-Control"] = "no-store"

    return router


def _response(state: SessionState) -> SessionResponse:
    return SessionResponse(
        user_id=str(state.user.id),
        login_id=str(state.user.login_id),
        display_name=state.user.display_name,
        role=state.user.role.value,
        permissions=[permission.value for permission in state.permissions],
        csrf_token=state.csrf_token,
        expires_at=state.expires_at,
    )
