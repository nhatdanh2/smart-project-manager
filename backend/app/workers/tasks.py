"""Celery tasks for background processing.

When ``USE_CELERY=true`` these are dispatched to a real worker
through Redis.  When it's false (default, dev mode) the routers
call them in-process so the user gets an immediate result.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# When Celery is disabled (dev), the shared ``celery_app`` is ``None``.
# We replace the ``@celery_app.task`` decorator with a tiny stub that
# still lets callers use ``.delay()`` / ``.apply_async()`` — they just
# execute synchronously.
# -----------------------------------------------------------------------------
class _InlineTask:
    """Synchronous stand-in for a Celery Task object.

    Lets code call ``.delay()`` and ``.apply_async()`` in dev (no
    worker) and have the function run inline.  ``bind=True`` tasks
    see ``self`` as the first arg; we transparently accept that.
    """

    def __init__(self, fn, *, bind=False):
        self.fn = fn
        self.name = getattr(fn, "__name__", "task")
        self.bind = bind

    def _invoke(self, *args, **kwargs):
        if self.bind:
            return self.fn(self, *args, **kwargs)
        return self.fn(*args, **kwargs)

    def delay(self, *args, **kwargs):
        return self._invoke(*args, **kwargs)

    def apply_async(self, args=None, kwargs=None, **_opts):  # noqa: D401
        return self._invoke(*(args or ()), **(kwargs or {}))

    def retry(self, exc=None, **_kwargs):  # noqa: D401
        # In inline mode there is no retry queue — just re-raise.
        raise exc if exc else RuntimeError(f"{self.name} failed")

    def __call__(self, *args, **kwargs):
        return self._invoke(*args, **kwargs)


def _task(*dargs, bind: bool = False, **dkwargs):
    def wrap(fn):
        if celery_app is not None:
            return celery_app.task(*dargs, **dkwargs)(fn)
        return _InlineTask(fn, bind=bind)

    return wrap


@_task(name="process_meeting_file")
def process_meeting_file(meeting_id: str) -> Dict[str, Any]:
    """Transcribe + extract tasks from a meeting upload.

    Implementation lives in routers/meetings.py for now; this stub keeps
    the worker surface stable so it can be triggered from Celery.
    """
    logger.info("process_meeting_file(%s)", meeting_id)
    return {"meeting_id": meeting_id, "status": "queued"}


@_task(name="recalculate_cpm", bind=True, max_retries=2)
def recalculate_cpm(self, project_id: str) -> Dict[str, Any]:
    """Recompute the Critical Path Method for a project and broadcast it.

    The actual calculation lives in ``app.services.cpm_service``;
    here we just plumb the DB session + WS broadcast.  The router
    uses the same code path synchronously when Celery isn't running.
    """
    try:
        from app.database import SessionLocal
        from app.models.task import Task
        from app.services.cpm_service import calculate_cpm, CPMTaskInput
        from app.services.realtime import broadcast_sync

        db = SessionLocal()
        try:
            tasks_q = db.query(Task).filter(Task.project_id == project_id).all()
            cpm = calculate_cpm(
                tasks=[
                    CPMTaskInput(
                        id=t.id,
                        title=t.title or "",
                        story_points=t.story_points or 1,
                        depends_on=t.depends_on or [],
                    )
                    for t in tasks_q
                ]
            )
            # Persist CPM fields back to the DB so the API/UI see
            # the updated critical-path flags immediately.
            by_id = {r.id: r for r in cpm.tasks}
            for t in tasks_q:
                r = by_id.get(t.id)
                if not r:
                    continue
                t.early_start = r.early_start
                t.early_finish = r.early_finish
                t.late_start = r.late_start
                t.late_finish = r.late_finish
                t.slack = r.slack
                t.is_critical = r.is_critical
            db.commit()
            broadcast_sync(
                project_id,
                {
                    "type": "cpm.recalculated",
                    "criticalPath": cpm.critical_path,
                    "projectDuration": cpm.project_duration,
                    "delayRisk": cpm.delay_risk,
                },
            )
            return {
                "project_id": project_id,
                "status": "done",
                "critical_path": cpm.critical_path,
                "project_duration": cpm.project_duration,
            }
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logger.exception("recalculate_cpm failed: %s", exc)
        raise self.retry(exc=exc, countdown=5)


@_task(name="calculate_all_contributions", bind=True, max_retries=2)
def calculate_all_contributions(self, project_id: str) -> Dict[str, Any]:
    """Recompute per-member contribution scores for a project.

    Writes a row to ``contribution_scores`` for every active member.
    Then broadcasts ``contributions.recalculated`` so the radar chart
    on the FE updates in real time.
    """
    try:
        from datetime import datetime, timezone

        from app.database import SessionLocal
        from app.models.contribution import ContributionScore
        from app.models.project import Project, ProjectMember
        from app.models.task import Task, TaskHistory
        from app.models.user import User
        from app.services.contribution_service import (
            calculate_contribution,
            MemberTaskStats,
        )
        from app.services.realtime import broadcast_sync

        db = SessionLocal()
        try:
            members = (
                db.query(User, ProjectMember)
                .join(ProjectMember, ProjectMember.user_id == User.id)
                .filter(ProjectMember.project_id == project_id)
                .all()
            )
            user_ids = [u.id for u, _ in members]
            tasks = db.query(Task).filter(Task.project_id == project_id).all()
            histories = (
                db.query(TaskHistory)
                .join(Task, Task.id == TaskHistory.task_id)
                .filter(Task.project_id == project_id)
                .all()
            )
            stats = []
            for user_id in user_ids:
                user_tasks = [t for t in tasks if t.assignee_id == user_id]
                completed = [t for t in user_tasks if t.status == "done"]
                on_time = 0
                for t in completed:
                    if t.deadline and t.completed_at:
                        dl = t.deadline if t.deadline.tzinfo else t.deadline.replace(tzinfo=timezone.utc)
                        ca = t.completed_at if t.completed_at.tzinfo else t.completed_at.replace(tzinfo=timezone.utc)
                        if ca <= dl:
                            on_time += 1
                user_histories = [h for h in histories if h.user_id == user_id]
                last_activity = None
                for h in user_histories:
                    if h.created_at and (not last_activity or h.created_at > last_activity):
                        last_activity = h.created_at
                stats.append(
                    MemberTaskStats(
                        user_id=user_id,
                        tasks_completed=len(completed),
                        tasks_assigned=len(user_tasks),
                        story_points_completed=sum(t.story_points for t in completed),
                        story_points_assigned=sum(t.story_points for t in user_tasks),
                        on_time_completed=on_time,
                        activity_count=len(user_histories),
                        last_activity=last_activity,
                    )
                )
            results = calculate_contribution(stats)
            now = datetime.now(timezone.utc)
            for r in results:
                row = (
                    db.query(ContributionScore)
                    .filter(
                        ContributionScore.project_id == project_id,
                        ContributionScore.user_id == r.user_id,
                    )
                    .first()
                )
                breakdown = {**r.breakdown, "percent": r.percent}
                if row:
                    row.score = r.score
                    row.breakdown = breakdown
                    row.calculated_at = now
                else:
                    db.add(
                        ContributionScore(
                            project_id=project_id,
                            user_id=r.user_id,
                            score=r.score,
                            breakdown=breakdown,
                            calculated_at=now,
                        )
                    )
            db.commit()
            broadcast_sync(
                project_id,
                {
                    "type": "contributions.recalculated",
                    "projectId": project_id,
                },
            )
            return {"project_id": project_id, "members": len(results), "status": "done"}
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logger.exception("calculate_all_contributions failed: %s", exc)
        raise self.retry(exc=exc, countdown=5)


@_task(name="app.workers.tasks.gdpr_purge_task")
def gdpr_purge_task() -> Dict[str, Any]:
    """Hard-delete accounts past the GDPR grace period.

    Scheduled by Celery beat (see ``celery_app.py``).  Returns the
    number of accounts purged so the operator can confirm.
    """
    from app.jobs.gdpr_purge_job import run_purge

    purged = run_purge()
    logger.info("gdpr_purge_task: purged %d account(s)", purged)
    return {"purged": purged}


@_task(name="app.workers.tasks.recurring_reminder_task")
def recurring_reminder_task() -> Dict[str, Any]:
    from app.jobs.recurring_task_job import spawn_due_recurring_tasks

    r = spawn_due_recurring_tasks()
    return {"inspected": r.inspected, "reminders_sent": r.reminders_sent}


@_task(name="app.workers.tasks.presence_cleanup_task")
def presence_cleanup_task() -> Dict[str, Any]:
    from app.jobs.presence_cleanup_job import kick_stale_presence

    kicked = kick_stale_presence()
    return {"projects_updated": kicked}


@_task(name="app.workers.tasks.search_reindex_task")
def search_reindex_task() -> Dict[str, Any]:
    from app.jobs.search_reindex_job import reindex_all

    return reindex_all()


@_task(name="app.workers.tasks.daily_digest_task")
def daily_digest_task() -> Dict[str, Any]:
    from app.jobs.daily_digest_job import send_daily_digests

    return send_daily_digests()


@_task(name="app.workers.tasks.webhook_deliver_task")
def webhook_deliver_task() -> Dict[str, Any]:
    from app.jobs.webhook_dispatch_job import deliver_pending

    return deliver_pending()


@_task(name="app.workers.tasks.ai_extract_meeting_task")
def ai_extract_meeting_task(meeting_id: str) -> Dict[str, Any]:
    from app.jobs.ai_extraction_job import extract_meeting_actions

    return extract_meeting_actions(meeting_id)
