"""Shared declarative metadata imported by Alembic."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared SQLAlchemy declarative base for reviewed persistence models."""
