"""Authenticated lexical knowledge endpoints."""

from fastapi import APIRouter, Cookie, Query, Response
from pydantic import BaseModel

from opsbridge.application.auth import AuthService
from opsbridge.application.errors import AuthenticationRequiredError
from opsbridge.application.knowledge import Citation, KnowledgeService
from opsbridge.presentation.http.routes.auth import SESSION_COOKIE


class CitationResponse(BaseModel):
    document_code: str
    document_title: str
    document_version: str
    chunk_id: str
    heading: str
    content: str
    score: float
    href: str


class KnowledgeSearchResponse(BaseModel):
    mode: str
    query: str
    abstained: bool
    citations: list[CitationResponse]


def create_knowledge_router(service: KnowledgeService, auth: AuthService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

    @router.get("/search", response_model=KnowledgeSearchResponse)
    def search(
        response: Response,
        q: str = Query(min_length=1, max_length=200),
        limit: int = Query(default=5, ge=1, le=10),
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> KnowledgeSearchResponse:
        if not session_token:
            raise AuthenticationRequiredError
        state = auth.session(session_token)
        result = service.search(query=q, role=state.user.role, limit=limit)
        response.headers["Cache-Control"] = "no-store"
        return KnowledgeSearchResponse(
            mode=result.mode,
            query=result.query,
            abstained=result.abstained,
            citations=[_citation(item) for item in result.citations],
        )

    @router.get("/documents/{document_code}/chunks/{chunk_id}", response_model=CitationResponse)
    def chunk(
        document_code: str,
        chunk_id: str,
        response: Response,
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> CitationResponse:
        if not session_token:
            raise AuthenticationRequiredError
        state = auth.session(session_token)
        result = service.chunk(document_code=document_code, chunk_id=chunk_id, role=state.user.role)
        response.headers["Cache-Control"] = "no-store"
        return _citation(result)

    return router


def _citation(item: Citation) -> CitationResponse:
    return CitationResponse(
        document_code=item.document_code,
        document_title=item.document_title,
        document_version=item.document_version,
        chunk_id=item.chunk_id,
        heading=item.heading,
        content=item.content,
        score=item.score,
        href=(f"/api/v1/knowledge/documents/{item.document_code}/chunks/{item.chunk_id}"),
    )
