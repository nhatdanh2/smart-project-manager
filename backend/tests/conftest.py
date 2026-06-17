"""Shared pytest fixtures."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Make ``app`` importable when running ``pytest`` from the repo root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Use a throwaway SQLite DB for tests; the helper main.py's init_db
# will create the schema on first call.
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mktemp(suffix='.db')}")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")  # don't count tests
os.environ.setdefault("ANTHROPIC_API_KEY", "")  # force stub


@pytest.fixture
def db():
    from app.database import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Wipe the DB so each test starts fresh
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
