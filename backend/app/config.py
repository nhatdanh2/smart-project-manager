"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List


BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class Settings:
    # App
    APP_NAME: str = "Smart Student Project Manager"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("1", "true", "yes")
    API_PREFIX: str = "/api"
    # Public-facing base URL — used for SAML / OIDC callbacks.
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

    # Database (default to local SQLite for dev, can override with Postgres URL)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'smart_project.db'}",
    )

    # Redis (optional - many features have in-memory fallback for dev)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    USE_CELERY: bool = os.getenv("USE_CELERY", "false").lower() in ("1", "true", "yes")

    # Auth
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production-please")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # AI - Anthropic
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    # AI - OpenAI (used for Whisper transcription)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "whisper-1")

    # File storage (we use local FS in dev; S3-compatible client can be added later)
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "")
    S3_REGION: str = os.getenv("S3_REGION", "ap-southeast-1")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")

    # CORS
    CORS_ORIGINS: List[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if o.strip()
    ]

    # Uploads
    UPLOAD_DIR: Path = UPLOAD_DIR
    MAX_UPLOAD_BYTES_TEXT: int = 10 * 1024 * 1024  # 10MB
    MAX_UPLOAD_BYTES_AUDIO: int = 50 * 1024 * 1024  # 50MB

    # Rate limiting (Phase 6)
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes")
    # Default per-route per-IP limit (used by the default decorator)
    RATE_LIMIT_DEFAULT: str = os.getenv("RATE_LIMIT_DEFAULT", "120/minute")
    # Strict limits for expensive endpoints (AI generation, uploads)
    RATE_LIMIT_AI: str = os.getenv("RATE_LIMIT_AI", "10/minute")
    RATE_LIMIT_UPLOAD: str = os.getenv("RATE_LIMIT_UPLOAD", "20/minute")
    RATE_LIMIT_AUTH: str = os.getenv("RATE_LIMIT_AUTH", "10/minute")

    # GDPR (Phase 10)
    GDPR_DELETION_GRACE_DAYS: int = int(os.getenv("GDPR_DELETION_GRACE_DAYS", "30"))

    # S3 / presigned URLs (Phase 10)
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "")  # leave empty for AWS
    S3_PRESIGN_EXPIRES_SECONDS: int = int(os.getenv("S3_PRESIGN_EXPIRES_SECONDS", "900"))

    # Meilisearch (Phase 10)
    MEILISEARCH_URL: str = os.getenv("MEILISEARCH_URL", "http://localhost:7700")
    MEILISEARCH_MASTER_KEY: str = os.getenv("MEILISEARCH_MASTER_KEY", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
