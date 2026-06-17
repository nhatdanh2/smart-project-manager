"""Periodic GDPR purge.

Run as a Celery beat task in production.  In dev you can also call
``python -m app.jobs.gdpr_purge_job`` once a day or wire it into a
cron.
"""
from __future__ import annotations

import logging

from app.database import SessionLocal
from app.services.gdpr_service import purge_expired_deletions


logger = logging.getLogger(__name__)


def run_purge() -> int:
    db = SessionLocal()
    try:
        return purge_expired_deletions(db)
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    n = run_purge()
    print(f"purged {n} account(s)")
