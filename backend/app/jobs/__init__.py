"""Scheduled jobs for Smart PM.

Each public function is a thin wrapper that creates a DB session,
runs the work, and closes the session.  They are designed to be
called from Celery tasks (``app.workers.tasks``) or directly from
the FastAPI startup hook in development.
"""
from app.jobs.recurring_task_job import (  # noqa: F401
    spawn_due_recurring_tasks,
    SpawnResult,
)
from app.jobs.presence_cleanup_job import kick_stale_presence  # noqa: F401
from app.jobs.search_reindex_job import reindex_all  # noqa: F401
from app.jobs.ai_extraction_job import extract_meeting_actions  # noqa: F401
from app.jobs.daily_digest_job import send_daily_digests  # noqa: F401
