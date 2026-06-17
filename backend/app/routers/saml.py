"""SAML 2.0 SSO endpoints.

* ``GET  /api/saml/login?relay_state=/`` — start the flow, redirect
  to the IdP.
* ``POST /api/saml/acs`` — IdP posts the SAMLResponse here.  We
  validate, JIT-provision, and 302 back to the SPA with a
  short-lived ``saml_jwt`` query token; the SPA exchanges it
  for the normal access/refresh token pair.
* ``GET  /api/saml/metadata`` — SP metadata XML (download or
  paste into the IdP).
* ``GET/POST /api/saml/settings`` — admin-only CRUD on the IdP
  config (in single-tenant mode there is exactly one row).
* ``GET  /api/saml/log`` — admin view of recent assertions.

The endpoints degrade to 503 if the ``python3-saml`` package is
not installed, so dev installs without SSO still work.
"""
from __future__ import annotations

import base64
import logging
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.saml import SAMLSettings
from app.models.user import User
from app.services.auth_service import create_access_token, get_current_user
from app.services.saml_service import (
    SAMLUnavailable,
    build_auth_request,
    get_or_create_settings,
    process_acs,
)


logger = logging.getLogger(__name__)


router = APIRouter(prefix=f"{settings.API_PREFIX}/saml", tags=["saml"])


@router.get("/status")
def saml_status(db: Session = Depends(get_db)):
    """Public, unauthenticated — the login page uses this to decide
    whether to show the "Sign in with SSO" button.
    """
    try:
        row = get_or_create_settings(db)
    except Exception:
        return {"enabled": False}
    return {"enabled": row.enabled == "true", "label": row.label}


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(403, detail="Admin role required")


def _pkg_or_503():
    try:
        from onelogin.saml2.settings import OneLogin_Saml2_Settings
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "python3-saml is not installed. "
                "Run `pip install python3-saml xmlsec lxml` to enable SSO."
            ),
        ) from exc
    return OneLogin_Saml2_Settings


# -----------------------------------------------------------------------------
# Browser-facing flow
# -----------------------------------------------------------------------------
@router.get("/login")
def saml_login(
    request: Request,
    relay_state: str = Query("/", description="Where to send the user after success"),
    tenant_id: str = Query("default"),
    db: Session = Depends(get_db),
):
    try:
        url = build_auth_request(db, tenant_id=tenant_id, relay_state=relay_state)
    except SAMLUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse(url=url, status_code=302)


@router.post("/acs")
async def saml_acs(
    request: Request,
    SAMLResponse: str = Form(...),  # noqa: N803 — SAML spec
    RelayState: Optional[str] = Form(None),  # noqa: N803
    db: Session = Depends(get_db),
):
    try:
        user, _ = process_acs(db, SAMLResponse, ip=request.client.host if request.client else None)
    except SAMLUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    # Issue a short-lived one-shot token, then redirect back to the
    # SPA which calls /saml/exchange to swap it for normal tokens.
    one_shot = create_access_token(
        user, expires_minutes=2, scope="saml_exchange"
    )
    next_path = RelayState or "/"
    sep = "&" if "?" in next_path else "?"
    redirect_url = (
        f"{settings.PUBLIC_BASE_URL.rstrip('/')}{next_path}"
        f"{sep}saml_jwt={urllib.parse.quote(one_shot)}"
    )
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/metadata")
def saml_metadata(
    db: Session = Depends(get_db),
    tenant_id: str = Query("default"),
):
    OneLogin_Saml2_Settings = _pkg_or_503()
    row = get_or_create_settings(db, tenant_id)
    from app.services.saml_service import _to_dict
    saml_settings = OneLogin_Saml2_Settings(settings=_to_dict(row), sp_validation_only=True)
    metadata = saml_settings.get_sp_metadata()
    errors = saml_settings.validate_metadata(metadata)
    if errors:
        raise HTTPException(500, detail=f"Invalid SP metadata: {errors}")
    return Response(content=metadata, media_type="application/xml")


# -----------------------------------------------------------------------------
# Frontend convenience: exchange a one-shot token for the normal pair
# -----------------------------------------------------------------------------
class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    user: dict


@router.post("/exchange", response_model=TokenPairOut)
def saml_exchange(
    saml_jwt: str = Query(...),
    db: Session = Depends(get_db),
):
    """Trade the short-lived JWT issued by /acs for the full token pair."""
    from app.services.auth_service import decode_token
    from app.services.auth_service import issue_refresh_token

    try:
        payload = decode_token(saml_jwt)
    except Exception:
        raise HTTPException(401, detail="Invalid or expired SAML token")
    if payload.get("scope") != "saml_exchange":
        raise HTTPException(401, detail="Token is not an SSO exchange token")
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(401, detail="User not found / disabled")
    access = create_access_token(user.id, name=user.name)
    refresh = issue_refresh_token(user)
    return TokenPairOut(
        access_token=access,
        refresh_token=refresh,
        user={"id": user.id, "email": user.email, "name": user.name, "role": user.role},
    )


# -----------------------------------------------------------------------------
# Admin: IdP configuration CRUD
# -----------------------------------------------------------------------------
class SAMLSettingsIn(BaseModel):
    label: Optional[str] = None
    enabled: bool = False
    idp_entity_id: Optional[str] = None
    idp_sso_url: Optional[str] = None
    idp_slo_url: Optional[str] = None
    idp_x509_cert: Optional[str] = None
    sp_entity_id: Optional[str] = None
    sp_acs_url: Optional[str] = None
    sp_x509_cert: Optional[str] = None
    sp_private_key: Optional[str] = None
    name_id_format: Optional[str] = None
    attribute_map: Optional[dict] = None
    jit_create_users: bool = True
    default_role: str = "student"
    allowed_email_domains: Optional[list] = None


class SAMLSettingsOut(BaseModel):
    tenant_id: str
    label: str
    enabled: bool
    idp_entity_id: Optional[str]
    idp_sso_url: Optional[str]
    idp_slo_url: Optional[str]
    sp_entity_id: Optional[str]
    sp_acs_url: Optional[str]
    name_id_format: str
    attribute_map: Optional[dict]
    jit_create_users: bool
    default_role: str
    allowed_email_domains: Optional[list]
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/settings", response_model=SAMLSettingsOut)
def get_settings(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current)
    row = get_or_create_settings(db)
    return row


@router.put("/settings", response_model=SAMLSettingsOut)
def put_settings(
    payload: SAMLSettingsIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current)
    row = get_or_create_settings(db)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k in ("enabled", "jit_create_users"):
            v = "true" if v else "false"
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row
