"""ASGI entry point for local development and deployment tooling."""

from opsbridge.presentation.http.app import create_app

app = create_app()

__all__ = ["app", "create_app"]
