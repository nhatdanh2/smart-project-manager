"""FastAPI application entry point."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import init_db
from app.observability import init_sentry, init_tracing, instrument_app
from app.rate_limit import limiter, rate_limit_exceeded_handler
from app.routers import (
    ai,
    auth,
    email_digest,
    files,
    gdpr,
    meetings,
    members,
    notifications,
    projects,
    push,
    saml,
    tasks,
    users,
    webhooks,
    ws,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Backend API for the Smart Student Project Manager.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Wire up rate limiting.  ``app.state.limiter`` is required by slowapi's
# internals; the exception handler returns a JSON 429.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    # In production the CORS_ORIGINS env var lists the deployed frontend
    # origin(s) explicitly.  In dev we still fall back to "*" so local
    # curl/postman tests keep working.
    allow_origins=settings.CORS_ORIGINS if not settings.DEBUG else settings.CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_sentry()
    init_tracing()
    instrument_app(app)
    init_db()
    # Best-effort: configure Meilisearch indexes.  Safe to call when
    # the service isn't running — the SDK returns None and we no-op.
    try:
        from app.services.search_service import ensure_indexes

        ensure_indexes()
    except Exception:
        pass
    logger.info("Database initialised at %s", settings.DATABASE_URL)


@app.exception_handler(Exception)
def unhandled_exception_handler(_, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    from app.observability import capture_exception

    capture_exception(exc)
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error", "error": str(exc)}
    )


@app.get("/", tags=["health"])
def root() -> dict:
    return {
        "name": settings.APP_NAME,
        "status": "ok",
        "docs": "/docs",
        "api": settings.API_PREFIX,
    }


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "healthy"}


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(members.router)
app.include_router(notifications.router)
app.include_router(meetings.router)
app.include_router(files.router)
app.include_router(ai.router)
app.include_router(email_digest.router)
app.include_router(gdpr.router)
app.include_router(webhooks.router)
app.include_router(webhooks.global_router)
app.include_router(saml.router)
app.include_router(push.router)
app.include_router(ws.router)


@app.exception_handler(Exception)
def unhandled_exception_handler(_, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error", "error": str(exc)}
    )
