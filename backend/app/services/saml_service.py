"""SAML 2.0 SSO service.

Wraps ``python3-saml`` and provides:

* ``get_settings_for_tenant(tenant_id)`` — read the configured
  IdP / SP from the DB
* ``build_auth_request(tenant_id, relay_state)`` — produce the
  AuthnRequest URL the browser should be redirected to
* ``process_acs(tenant_id, saml_response_b64, relay_state)`` —
  validate the IdP assertion, JIT-provision the user, log the
  attempt, and return an internal JWT for the SPA to consume

The service degrades gracefully if the ``python3-saml`` package
isn't installed — endpoints then return 503 with a clear
message, and the regular email/password login keeps working.
"""
from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models.saml import SAMLSettings, SAMLAssertionLog
from app.models.user import User
from app.services.auth_service import create_access_token


logger = logging.getLogger(__name__)


class SAMLUnavailable(RuntimeError):
    """Raised when python3-saml is not installed."""


def _sdk():
    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
        from onelogin.saml2.utils import OneLogin_Saml2_Utils
    except ImportError as exc:  # pragma: no cover
        raise SAMLUnavailable(
            "python3-saml is not installed. "
            "Run `pip install python3-saml xmlsec lxml` and restart."
        ) from exc
    return OneLogin_Saml2_Auth, OneLogin_Saml2_Utils


def get_or_create_settings(db: Session, tenant_id: str = "default") -> SAMLSettings:
    row = db.query(SAMLSettings).filter(SAMLSettings.tenant_id == tenant_id).first()
    if row:
        return row
    row = SAMLSettings(
        tenant_id=tenant_id,
        label="Default SSO",
        enabled="false",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _to_dict(row: SAMLSettings) -> Dict[str, Any]:
    return {
        "strict": False,
        "debug": False,
        "sp": {
            "entityId": row.sp_entity_id or f"{settings.PUBLIC_BASE_URL}/api/saml/metadata",
            "assertionConsumerService": {
                "url": row.sp_acs_url or f"{settings.PUBLIC_BASE_URL}/api/saml/acs",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": row.name_id_format,
            "x509cert": row.sp_x509_cert or "",
            "privateKey": row.sp_private_key or "",
        },
        "idp": {
            "entityId": row.idp_entity_id or "",
            "singleSignOnService": {
                "url": row.idp_sso_url or "",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "singleLogoutService": (
                {"url": row.idp_slo_url, "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"}
                if row.idp_slo_url else {}
            ),
            "x509cert": row.idp_x509_cert or "",
        },
    }


def build_auth_request(
    db: Session,
    tenant_id: str = "default",
    relay_state: str = "/",
) -> str:
    """Return the URL the browser should be redirected to."""
    OneLogin_Saml2_Auth, _ = _sdk()
    row = get_or_create_settings(db, tenant_id)
    if row.enabled != "true":
        raise ValueError("SAML is not enabled for this tenant")
    if not row.idp_sso_url:
        raise ValueError("IdP SSO URL is not configured")
    req = OneLogin_Saml2_Auth(
        request_data={"https": "on", "http_host": settings.PUBLIC_BASE_URL},
        old_settings=_to_dict(row),
    )
    return req.login(return_to=relay_state)


def _extract_attributes(attributes: Dict[str, list]) -> Dict[str, str]:
    """Flatten the IdP attributes (which are always lists)."""
    out: Dict[str, str] = {}
    for k, v in attributes.items():
        if v:
            out[k.lower()] = str(v[0])
    return out


def process_acs(
    db: Session,
    saml_response_b64: str,
    ip: Optional[str] = None,
    tenant_id: str = "default",
) -> Tuple[User, str]:
    """Validate the IdP assertion, JIT-provision, return (user, jwt)."""
    OneLogin_Saml2_Auth, _ = _sdk()
    row = get_or_create_settings(db, tenant_id)

    def _record(action: str, name_id: Optional[str] = None, user_id: Optional[str] = None, reason: Optional[str] = None) -> None:
        db.add(SAMLAssertionLog(
            tenant_id=tenant_id,
            name_id=name_id,
            user_id=user_id,
            action=action,
            reason=reason,
            ip_address=ip,
        ))

    req = OneLogin_Saml2_Auth(
        request_data={"https": "on", "http_host": settings.PUBLIC_BASE_URL, "post_data": {"SAMLResponse": saml_response_b64}},
        old_settings=_to_dict(row),
    )
    req.process_response()
    errors = req.get_errors()
    if errors:
        reason = "; ".join(f"{k}={v}" for k, v in errors.items())
        _record("rejected", reason=reason[:500])
        db.commit()
        raise ValueError(f"SAML validation failed: {reason}")

    if not req.is_authenticated():
        _record("rejected", reason="not_authenticated")
        db.commit()
        raise ValueError("SAML response not authenticated")

    name_id = req.get_nameid()
    attributes = _extract_attributes(req.get_attributes())

    # Look up the SAML attribute map (or default to email/name/role)
    attr_map = row.attribute_map or {}
    email = attributes.get(attr_map.get("email", "email")) or name_id
    if not email or "@" not in email:
        _record("rejected", name_id=name_id, reason="no_email")
        db.commit()
        raise ValueError("SAML assertion does not include a usable email")
    name = attributes.get(attr_map.get("name", "name")) or email.split("@")[0]
    role = attributes.get(attr_map.get("role", "role")) or row.default_role

    # Domain allowlist
    if row.allowed_email_domains:
        domain = email.split("@", 1)[1].lower()
        if domain not in {d.lower() for d in row.allowed_email_domains}:
            _record("rejected", name_id=name_id, reason=f"domain_not_allowed:{domain}")
            db.commit()
            raise ValueError(f"Email domain {domain} is not allowed")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        if row.jit_create_users != "true":
            _record("rejected", name_id=name_id, reason="jit_disabled")
            db.commit()
            raise ValueError("JIT user creation is disabled")
        user = User(
            email=email,
            name=name,
            password_hash="!" + uuid.uuid4().hex,  # never used; SSO only
            role=role if role in ("student", "instructor", "admin") else "student",
        )
        db.add(user)
        db.flush()
        _record("jit", name_id=name_id, user_id=user.id)
    else:
        # Update name/role on every login (cheap; lets admins re-assign)
        if name and user.name != name:
            user.name = name
        if role and user.role != role and role in ("student", "instructor", "admin"):
            user.role = role
        db.add(user)
        _record("login", name_id=name_id, user_id=user.id)

    if not user.is_active:
        _record("rejected", name_id=name_id, user_id=user.id, reason="account_disabled")
        db.commit()
        raise ValueError("Account is disabled")

    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, name=user.name, extra={"scope": "saml_exchange"})
    return user, token
