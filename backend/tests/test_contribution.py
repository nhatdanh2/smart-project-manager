"""Smoke tests for the contribution service."""
from datetime import datetime, timedelta, timezone

from app.services.contribution_service import MemberTaskStats, calculate_contribution


def test_balanced_team():
    now = datetime.now(tz=timezone.utc)
    stats = [
        MemberTaskStats(
            user_id="u1",
            tasks_completed=5,
            tasks_assigned=5,
            story_points_completed=10,
            story_points_assigned=10,
            on_time_completed=5,
            activity_count=10,
            last_activity=now,
        ),
        MemberTaskStats(
            user_id="u2",
            tasks_completed=5,
            tasks_assigned=5,
            story_points_completed=10,
            story_points_assigned=10,
            on_time_completed=5,
            activity_count=10,
            last_activity=now,
        ),
    ]
    results = calculate_contribution(stats)
    assert len(results) == 2
    # Roughly balanced -> ~50% each
    for r in results:
        assert 45 <= r.percent <= 55
        assert r.is_ghost is False


def test_ghost_member_detected():
    now = datetime.now(tz=timezone.utc)
    stats = [
        MemberTaskStats(
            user_id="active",
            tasks_completed=10,
            tasks_assigned=10,
            story_points_completed=20,
            story_points_assigned=20,
            on_time_completed=10,
            activity_count=20,
            last_activity=now,
        ),
        MemberTaskStats(
            user_id="ghost",
            tasks_completed=0,
            tasks_assigned=2,
            story_points_completed=0,
            story_points_assigned=4,
            on_time_completed=0,
            activity_count=0,
            last_activity=now - timedelta(days=14),
        ),
    ]
    results = calculate_contribution(stats)
    ghost = next(r for r in results if r.user_id == "ghost")
    assert ghost.is_ghost is True
    assert ghost.percent < 5
