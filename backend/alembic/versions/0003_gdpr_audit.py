"""gdpr: audit log table

Revision ID: 0003_gdpr_audit
Revises: 0002_gdpr_soft_delete
Create Date: 2026-06-15 12:30:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0003_gdpr_audit"
down_revision: Union[str, None] = "0002_gdpr_soft_delete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gdpr_audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("affected_user_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_gdpr_audit_affected_user_id", "gdpr_audit_logs", ["affected_user_id"])
    op.create_index("ix_gdpr_audit_action", "gdpr_audit_logs", ["action"])


def downgrade() -> None:
    op.drop_index("ix_gdpr_audit_action", table_name="gdpr_audit_logs")
    op.drop_index("ix_gdpr_audit_affected_user_id", table_name="gdpr_audit_logs")
    op.drop_table("gdpr_audit_logs")
