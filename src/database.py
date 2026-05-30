"""
Database engine & session factory.

Reads ``DATABASE_URL`` from the environment (or ``.env`` file) and falls
back to a local SQLite file when nothing is set.

Usage::

    from src.database import get_db

    @app.get("/items")
    async def list_items(db: Session = Depends(get_db)):
        ...
"""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./personal_os.db")

# SQLite needs check_same_thread=False when used with FastAPI's thread pool.
connect_args: dict = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # Verify connections before handing them out
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a scoped SQLAlchemy session.

    The session is committed on success and rolled back + closed on error.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
