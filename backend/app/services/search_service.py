"""Meilisearch client + index management.

Indexes we maintain:

* ``tasks``       — every task across every project
* ``meetings``    — meeting titles + transcripts

We don't ship search-as-you-type analytics (queries, no-results) in
this iteration; the Meilisearch dashboard covers that for now.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

from app.config import settings


logger = logging.getLogger(__name__)


TASKS_INDEX = "tasks"
MEETINGS_INDEX = "meetings"


@lru_cache(maxsize=1)
def _client():
    """Lazy-import ``meilisearch`` and return a configured client.

    Returns ``None`` if the SDK isn't installed or the URL is empty
    so callers can degrade.
    """
    if not settings.MEILISEARCH_URL:
        return None
    try:
        import meilisearch
    except ImportError:
        logger.warning("meilisearch SDK not installed; search disabled")
        return None
    return meilisearch.Client(
        settings.MEILISEARCH_URL,
        settings.MEILISEARCH_MASTER_KEY or None,
    )


def is_enabled() -> bool:
    return _client() is not None


def ensure_indexes() -> None:
    """Create / update the indexes and set searchable / filterable attributes.

    Safe to call repeatedly; Meilisearch treats this as a no-op when
    the settings are unchanged.
    """
    client = _client()
    if client is None:
        return
    # Tasks
    try:
        client.create_index(TASKS_INDEX, {"primaryKey": "id"})
    except Exception:
        pass
    try:
        client.index(TASKS_INDEX).update_settings(
            {
                "searchableAttributes": ["title", "description", "project_title"],
                "filterableAttributes": ["project_id", "status", "assignee_id"],
                "sortableAttributes": ["created_at", "deadline"],
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("meilisearch tasks settings update failed: %s", exc)

    # Meetings
    try:
        client.create_index(MEETINGS_INDEX, {"primaryKey": "id"})
    except Exception:
        pass
    try:
        client.index(MEETINGS_INDEX).update_settings(
            {
                "searchableAttributes": ["title", "transcript"],
                "filterableAttributes": ["project_id", "status"],
                "sortableAttributes": ["created_at"],
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("meilisearch meetings settings update failed: %s", exc)


# -----------------------------------------------------------------------------
# Indexing helpers
# -----------------------------------------------------------------------------
def index_task(task: Dict[str, Any]) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.index(TASKS_INDEX).add_documents([task])
    except Exception as exc:  # noqa: BLE001
        logger.warning("meilisearch index_task failed: %s", exc)


def update_task(task_id: str, partial: Dict[str, Any]) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.index(TASKS_INDEX).update_documents([{"id": task_id, **partial}])
    except Exception as exc:  # noqa: BLE001
        logger.warning("meilisearch update_task failed: %s", exc)


def delete_task(task_id: str) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.index(TASKS_INDEX).delete_document(task_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("meilisearch delete_task failed: %s", exc)


def index_meeting(meeting: Dict[str, Any]) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.index(MEETINGS_INDEX).add_documents([meeting])
    except Exception as exc:  # noqa: BLE001
        logger.warning("meilisearch index_meeting failed: %s", exc)


def delete_meeting(meeting_id: str) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.index(MEETINGS_INDEX).delete_document(meeting_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("meilisearch delete_meeting failed: %s", exc)


# -----------------------------------------------------------------------------
# Query helpers
# -----------------------------------------------------------------------------
def search(
    query: str,
    *,
    index: str = TASKS_INDEX,
    project_id: Optional[str] = None,
    extra_filters: Optional[List[str]] = None,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    client = _client()
    if client is None:
        return {"hits": [], "estimatedTotalHits": 0, "disabled": True}
    filters: List[str] = []
    if project_id:
        filters.append(f'project_id = "{project_id}"')
    if extra_filters:
        filters.extend(extra_filters)
    return client.index(index).search(
        query,
        {
            "limit": limit,
            "offset": offset,
            "filter": filters or None,
        },
    ).to_dict()
