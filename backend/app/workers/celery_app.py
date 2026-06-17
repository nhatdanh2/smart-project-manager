"""Celery application factory.

The actual workers (process_meeting_file, recalculate_cpm,
calculate_all_contributions) are registered but the application only
attaches to a real broker when ``USE_CELERY=true``.  By default the
backend runs jobs inline so the dev experience is zero-config.
"""
from __future__ import annotations

import logging

from app.config import settings


logger = logging.getLogger(__name__)


def build_celery():
    """Lazy Celery factory - imported only when USE_CELERY is enabled."""
    from celery import Celery

    app = Celery(
        "smart_project_manager",
        broker=settings.REDIS_URL,
        backend=settings.REDIS_URL,
        include=["app.workers.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        # Beat schedule — runs on the worker marked with -B
        beat_schedule={
            "gdpr.purge_expired": {
                "task": "app.workers.tasks.gdpr_purge_task",
                "schedule": 24 * 60 * 60,  # daily
            },
            "recurring_task.reminder": {
                "task": "app.workers.tasks.recurring_reminder_task",
                "schedule": 60 * 60,  # hourly
            },
            "presence.cleanup": {
                "task": "app.workers.tasks.presence_cleanup_task",
                "schedule": 30,  # every 30s
            },
            "search.reindex": {
                "task": "app.workers.tasks.search_reindex_task",
                # Once a day at 04:30 UTC
                "schedule": 24 * 60 * 60,
            },
            "daily_digest.send": {
                "task": "app.workers.tasks.daily_digest_task",
                "schedule": 24 * 60 * 60,  # daily
            },
            "webhook.deliver": {
                "task": "app.workers.tasks.webhook_deliver_task",
                "schedule": 30,
            },
        },
    )
    return app


celery_app = build_celery() if settings.USE_CELERY else None
