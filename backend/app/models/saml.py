"""Per-tenant SAML IdP configuration + JIT-provisioned user links.

A tenant in our world is "the org" — most installs run a single
SAML config; multi-tenant is left as future work (one row per
``tenant_id`` is enough for the schema).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SAMLSettings(Base):
    __tablename__ = "saml_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True, default="default"
    )
    # Display label (e.g. "ACME University SSO")
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="Default SSO")
    enabled: Mapped[bool] = mapped_column(String(10), default="true", nullable=False)  # SQLite stores bool as text
    # ---- IdP side ----
    idp_entity_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    idp_sso_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    idp_slo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    idp_x509_cert: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # ---- SP side (auto-generated at install time) ----
    sp_entity_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sp_acs_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sp_x509_cert: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sp_private_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # ---- Mapping ----
    name_id_format: Mapped[str] = mapped_column(
        String(255), default="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress", nullable=False
    )
    attribute_map: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # {"email": "urn:oid:0.9.2342.19200300.100.1.3",
    #  "name":  "urn:oid:2.5.4.42",
    #  "role":  "urn:oid:1.3.6.1.4.1.5923.1.1.1.7"}
    # ---- JIT config ----
    jit_create_users: Mapped[str] = mapped_column(String(5), default="true", nullable=False)
    default_role: Mapped[str] = mapped_column(String(20), default="student", nullable=False)
    allowed_email_domains: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SAMLAssertionLog(Base):
    __tablename__ = "saml_assertion_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # "login" | "jit" | "rejected"
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
