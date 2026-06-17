"""Contribution score calculation.

Implements the weighted formula from the PRD.  All inputs come from the
caller (a DB session) so this service remains pure and easily testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class MemberTaskStats:
    user_id: str
    tasks_completed: int
    tasks_assigned: int
    story_points_completed: int
    story_points_assigned: int
    on_time_completed: int
    activity_count: int
    last_activity: Optional[datetime]


@dataclass
class ContributionResult:
    user_id: str
    score: float
    percent: float
    breakdown: Dict[str, float]
    is_ghost: bool
    last_activity_days_ago: Optional[int]


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def calculate_contribution(
    members: List[MemberTaskStats],
    *,
    ghost_threshold_days: int = 7,
    now: Optional[datetime] = None,
) -> List[ContributionResult]:
    """Compute contribution score for each member and convert to percent.

    Formula:
        raw = task*0.4 + story_point*0.35 + on_time*0.15 + activity*0.1
    """
    now_ = now or datetime.now(tz=timezone.utc)

    if not members:
        return []

    team_completed = sum(m.tasks_completed for m in members) or 0
    team_sp = sum(m.story_points_completed for m in members) or 0
    team_activity = sum(m.activity_count for m in members) or 0

    raw_scores: List[ContributionResult] = []
    for m in members:
        task_score = _safe_ratio(m.tasks_completed, max(team_completed, 1))
        sp_score = _safe_ratio(m.story_points_completed, max(team_sp, 1))
        on_time_score = _safe_ratio(m.on_time_completed, m.tasks_completed)
        activity_score = _safe_ratio(m.activity_count, max(team_activity, 1))

        score = (
            task_score * 0.40
            + sp_score * 0.35
            + on_time_score * 0.15
            + activity_score * 0.10
        )
        score = round(score, 4)

        last_activity_days_ago: Optional[int] = None
        is_ghost = False
        if m.last_activity is not None:
            last = m.last_activity if m.last_activity.tzinfo else m.last_activity.replace(
                tzinfo=timezone.utc
            )
            last_activity_days_ago = max(0, (now_ - last).days)
            is_ghost = last_activity_days_ago >= ghost_threshold_days

        raw_scores.append(
            ContributionResult(
                user_id=m.user_id,
                score=score,
                percent=0.0,  # filled below
                breakdown={
                    "task_score": round(task_score, 4),
                    "story_point_score": round(sp_score, 4),
                    "on_time_score": round(on_time_score, 4),
                    "activity_score": round(activity_score, 4),
                    "tasks_completed": m.tasks_completed,
                    "tasks_assigned": m.tasks_assigned,
                    "story_points_completed": m.story_points_completed,
                    "story_points_assigned": m.story_points_assigned,
                    "on_time_rate": round(on_time_score, 4),
                    "activity_count": m.activity_count,
                    "last_activity_days_ago": last_activity_days_ago,
                    "is_ghost": is_ghost,
                },
                is_ghost=is_ghost,
                last_activity_days_ago=last_activity_days_ago,
            )
        )

    total_score = sum(r.score for r in raw_scores) or 1.0
    for r in raw_scores:
        r.percent = round((r.score / total_score) * 100, 2)
    return raw_scores
