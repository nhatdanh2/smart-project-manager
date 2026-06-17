"""Rate limiting setup (slowapi)."""
from __future__ import annotations

import logging

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings


logger = logging.getLogger(__name__)


def _key(request: Request) -> str:
    """Pick a per-user key when a token is available, otherwise per-IP.

    This gives authenticated users a higher personalised quota (their
    access token's sub claim) and falls back to IP for unauthenticated
    traffic (login/register, webhooks, etc.).
    """
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        try:
            from app.services.auth_service import decode_token

            payload = decode_token(auth.split(" ", 1)[1])
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass
    return f"ip:{get_remote_address(request)}"


# Build the limiter.  Use the default in-memory storage; swap for Redis
# by passing ``storage_uri=settings.REDIS_URL`` when scaling out.
limiter = Limiter(
    key_func=_key,
    default_limits=[settings.RATE_LIMIT_DEFAULT] if settings.RATE_LIMIT_ENABLED else [],
    enabled=settings.RATE_LIMIT_ENABLED,
    # NOTE: slowapi's ``headers_enabled=True`` requires every limited
    # endpoint to accept a ``response: Response`` parameter.  Our
    # routers don't always do that, which would cause a 500 on every
    # rate-limited call.  We disable it — the X-RateLimit-* headers
    # aren't on the PRD's critical path.
    headers_enabled=False,
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom 429 response so the message is JSON-shaped for the frontend.

    slowapi's handler signature is ``(request, exc)`` and may return a
    plain Response — we return a ``JSONResponse`` so the FE can parse
    ``detail`` directly.
    """
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}",
            "limit": str(exc.detail),
        },
    )
