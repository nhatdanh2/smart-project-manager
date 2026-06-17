"""Initial empty migration - schema is auto-created for SQLite dev.

Run ``alembic revision --autogenerate -m "init"`` later for PostgreSQL.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
