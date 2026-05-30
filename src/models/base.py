"""
Declarative base for all SQLAlchemy models.

Every model in Personal OS inherits from this Base so that Alembic's
`target_metadata` can discover the full schema from a single import.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base class for all ORM models."""

    pass
