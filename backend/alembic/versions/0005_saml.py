"""saml: settings + assertion log

Revision ID: 0005_saml
Revises: 0004_webhooks
Create Date: 2026-06-15 14:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0005_saml"
down_revision: Union[str, None] = "0004_webhooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saml_settings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("label", sa.String(length=255), nullable=False, server_default="Default SSO"),
        sa.Column("enabled", sa.String(length=10), nullable=False, server_default="true"),
        sa.Column("idp_entity_id", sa.String(length=500), nullable=True),
        sa.Column("idp_sso_url", sa.String(length=500), nullable=True),
        sa.Column("idp_slo_url", sa.String(length=500), nullable=True),
        sa.Column("idp_x509_cert", sa.Text(), nullable=True),
        sa.Column("sp_entity_id", sa.String(length=500), nullable=True),
        sa.Column("sp_acs_url", sa.String(length=500), nullable=True),
        sa.Column("sp_x509_cert", sa.Text(), nullable=True),
        sa.Column("sp_private_key", sa.Text(), nullable=True),
        sa.Column(
            "name_id_format",
            sa.String(length=255),
            nullable=False,
            server_default="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        ),
        sa.Column("attribute_map", sa.JSON(), nullable=True),
        sa.Column("jit_create_users", sa.String(length=5), nullable=False, server_default="true"),
        sa.Column("default_role", sa.String(length=20), nullable=False, server_default="student"),
        sa.Column("allowed_email_domains", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_saml_settings_tenant_id", "saml_settings", ["tenant_id"])

    op.create_table(
        "saml_assertion_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("name_id", sa.String(length=255), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_saml_assertion_logs_tenant_id", "saml_assertion_logs", ["tenant_id"])
    op.create_index("ix_saml_assertion_logs_user_id", "saml_assertion_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_saml_assertion_logs_user_id", table_name="saml_assertion_logs")
    op.drop_index("ix_saml_assertion_logs_tenant_id", table_name="saml_assertion_logs")
    op.drop_table("saml_assertion_logs")
    op.drop_index("ix_saml_settings_tenant_id", table_name="saml_settings")
    op.drop_table("saml_settings")
