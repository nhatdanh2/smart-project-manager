"""Activity tracking helpers used by the heat map and digest."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from app.models.task import Task, TaskHistory


def build_activity_heatmap(
    db: Session, project_id: str, weeks: int = 12
) -> Tuple[List[Dict], int, Dict[str, List[Dict]]]:
    """Return a heat map of task-history events grouped by day.

    Returns (cells, total, per_user_cells) where cells is a flat list of
    {date, count} covering the last `weeks` weeks (Mon-Sun grid), total is
    the sum of all counts, and per_user_cells is a dict user_id -> list of
    cells for that user.
    """
    weeks = max(1, min(weeks, 52))
    today = datetime.now(tz=timezone.utc).date()
    # Align to start of week (Monday)
    start_of_week = today - timedelta(days=today.weekday())
    start = start_of_week - timedelta(weeks=weeks - 1)

    histories = (
        db.query(TaskHistory)
        .join(Task, Task.id == TaskHistory.task_id)
        .filter(
            Task.project_id == project_id,
            TaskHistory.created_at >= start,
        )
        .all()
    )

    per_user_day: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    day_count: Dict[str, int] = defaultdict(int)

    for h in histories:
        d = h.created_at.date()
        key = d.isoformat()
        day_count[key] += 1
        if h.user_id:
            per_user_day[h.user_id][key] += 1

    # Fill in all days in the range so the grid is dense
    cells: List[Dict] = []
    cur = start
    while cur <= today:
        key = cur.isoformat()
        cells.append({"date": key, "count": day_count.get(key, 0)})
        cur += timedelta(days=1)

    per_user: Dict[str, List[Dict]] = {}
    for uid, daymap in per_user_day.items():
        per_user[uid] = [
            {"date": c["date"], "count": daymap.get(c["date"], 0)} for c in cells
        ]

    total = sum(c["count"] for c in cells)
    return cells, total, per_user
