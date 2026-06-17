"""SQLAlchemy engine, session, and Base declarative class."""
from __future__ import annotations

import logging
import os
from typing import Generator

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


logger = logging.getLogger(__name__)


def _make_engine():
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        # SQLite needs check_same_thread=False to work with FastAPI's threadpool
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
    return create_engine(url, pool_pre_ping=True, echo=False)


engine = _make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _has_alembic_version_table() -> bool:
    """Return True if ``alembic_version`` exists, i.e. migrations are being used."""
    try:
        insp = inspect(engine)
        return "alembic_version" in insp.get_table_names()
    except Exception:
        return False


def init_db() -> None:
    """Create all tables.

    Behaviour:
    * If the DB already has an ``alembic_version`` table (i.e. the
      operator is using migrations), this is a no-op so we never
      accidentally create tables that drift from the migrations.
    * If the DB is empty, this builds the schema.  Convenient for
      SQLite dev / unit tests where running Alembic by hand is
      friction.  Production deployments should use
      ``alembic upgrade head`` instead.
    """
    from app import models  # noqa: F401  -- import to register models

    if _has_alembic_version_table():
        logger.info(
            "Alembic migrations detected — skipping create_all to avoid drift. "
            "Use `alembic upgrade head` to apply schema changes."
        )
        return
    Base.metadata.create_all(bind=engine)
