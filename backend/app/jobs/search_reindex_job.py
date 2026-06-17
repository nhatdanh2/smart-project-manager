"""Bulk reindex Meilisearch from Postgres.

Useful after restoring a backup, or when Meilisearch was offline
and missed updates.  Replaces all documents in the ``tasks`` and
``meetings`` indexes with the current state.

Run with: ``python -m app.jobs.search_reindex_job``
"""
from __future__ import annotations

import logging
from typing import Iterable

from app.database import SessionLocal
from app.models.meeting import Meeting
from app.models.project import Project
from app.models.task import Task
from app.services.search_service import (
    delete_meeting,
    delete_task,
    index_meeting,
    index_task,
    is_enabled,
)


logger = logging.getLogger(__name__)


def _iter_tasks(db) -> Iterable[Task]:
    # Stream in pages so we don't load the whole table into memory.
    offset = 0
    page = 500
    while True:
        rows = db.query(Task).order_by(Task.created_at).offset(offset).limit(page).all()
        if not rows:
            return
        for r in rows:
            yield r
        offset += page


def _iter_meetings(db) -> Iterable[Meeting]:
    offset = 0
    page = 500
    while True:
        rows = db.query(Meeting).order_by(Meeting.created_at).offset(offset).limit(page).all()
        if not rows:
            return
        for r in rows:
            yield r
        offset += page


def reindex_all() -> dict:
    if not is_enabled():
        logger.warning("Meilisearch is not configured; nothing to do")
        return {"indexed_tasks": 0, "indexed_meetings": 0, "backend": "disabled"}

    db = SessionLocal()
    try:
        # Build a {project_id: title} cache
        project_titles = {p.id: p.title for p in db.query(Project).all()}

        n_tasks = 0
        for t in _iter_tasks(db):
            index_task(
                {
                    "id": t.id,
                    "project_id": t.project_id,
                    "title": t.title,
                    "description": t.description or "",
                    "status": t.status,
                    "assignee_id": t.assignee_id or "",
                    "project_title": project_titles.get(t.project_id, ""),
                    "created_at": int(t.created_at.timestamp()) if t.created_at else 0,
                    "deadline": int(t.deadline.timestamp()) if t.deadline else 0,
                }
            )
            n_tasks += 1

        n_meetings = 0
        for m in _iter_meetings(db):
            index_meeting(
                {
                    "id": m.id,
                    "project_id": m.project_id,
                    "title": m.title or "",
                    "transcript": (m.transcript or "")[:10_000],
                    "status": m.status,
                    "created_at": int(m.created_at.timestamp()) if m.created_at else 0,
                }
            )
            n_meetings += 1

        logger.info(
            "search_reindex: indexed %d tasks + %d meetings", n_tasks, n_meetings
        )
        return {
            "indexed_tasks": n_tasks,
            "indexed_meetings": n_meetings,
            "backend": "meilisearch",
        }
    finally:
        db.close()


def clear_all() -> None:
    """Drop every document.  Use with care — only for fresh installs."""
    for t_id, _ in ((t.id, None) for t in []):
        delete_task(t_id)
    # Simpler: use Meilisearch's own clear endpoint
    from app.services.search_service import _client
    client = _client()
    if client:
        try:
            client.index("tasks").delete_all_documents()
            client.index("meetings").delete_all_documents()
        except Exception:
            pass


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    print(reindex_all())
