"""Members router: list members with contribution scores."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskHistory
from app.models.user import User
from app.schemas.project import MemberOut
from app.schemas.user import ActivityCell, ActivityHeatmapOut
from app.services.activity_service import build_activity_heatmap
from app.services.auth_service import get_current_user
from app.services.contribution_service import (
    ContributionResult,
    MemberTaskStats,
    calculate_contribution,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix=f"{settings.API_PREFIX}/projects", tags=["members"])


@router.get("/{project_id}/contributions", response_model=List[MemberOut])
def list_contributions(
    project_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[MemberOut]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pm = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current.id,
        )
        .first()
    )
    if not pm:
        raise HTTPException(status_code=403, detail="Not a project member")

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

    stats: List[MemberTaskStats] = []
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
        last_activity = max(
            ([h.created_at for h in user_histories] + [t.updated_at for t in user_tasks if getattr(t, "updated_at", None)]),
            default=None,
        )
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

    results: List[ContributionResult] = calculate_contribution(stats)

    user_by_id = {u.id: u for u, _ in members}
    member_role = {u.id: pm_role.role for u, pm_role in members}

    out: List[MemberOut] = []
    for r in results:
        u = user_by_id.get(r.user_id)
        if not u:
            continue
        out.append(
            MemberOut(
                user_id=u.id,
                name=u.name,
                email=u.email,
                role=member_role.get(u.id, "member"),
                contribution_percent=r.percent,
            )
        )
    return out


@router.get("/{project_id}/assignable", response_model=List[MemberOut])
def list_assignable(
    project_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[MemberOut]:
    """Return the list of project members (lighter than /contributions)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pm = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current.id,
        )
        .first()
    )
    if not pm:
        raise HTTPException(status_code=403, detail="Not a project member")
    members = (
        db.query(User)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .filter(ProjectMember.project_id == project_id)
        .order_by(User.name.asc())
        .all()
    )
    out: List[MemberOut] = []
    for u in members:
        out.append(
            MemberOut(
                user_id=u.id,
                name=u.name,
                email=u.email,
                role=(
                    db.query(ProjectMember)
                    .filter(
                        ProjectMember.project_id == project_id,
                        ProjectMember.user_id == u.id,
                    )
                    .first()
                    .role
                ),
                contribution_percent=None,
            )
        )
    return out


# -----------------------------------------------------------------------------
# Membership management (instructor / leader can add & remove members)
# -----------------------------------------------------------------------------
class AddMemberIn(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: str = "member"


@router.post("/{project_id}/members", status_code=201)
def add_member(
    project_id: str,
    payload: AddMemberIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Add a user to a project.

    Either ``user_id`` or ``email`` is required.  Only the project
    instructor or an admin can add members.
    """
    from pydantic import BaseModel as _BM

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, detail="Project not found")
    caller_pm = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current.id,
        )
        .first()
    )
    if not (current.role == "admin" or (caller_pm and caller_pm.role in ("leader", "instructor"))):
        raise HTTPException(403, detail="Only the project owner can add members")

    target: Optional[User] = None
    if payload.user_id:
        target = db.query(User).filter(User.id == payload.user_id).first()
    elif payload.email:
        target = db.query(User).filter(User.email == payload.email).first()
    if not target:
        raise HTTPException(404, detail="User not found")
    if not target.is_active:
        raise HTTPException(400, detail="Cannot add a deactivated user")
    existing = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == target.id,
        )
        .first()
    )
    if existing:
        return {"status": "already_member", "user_id": target.id}

    db.add(
        ProjectMember(
            project_id=project_id,
            user_id=target.id,
            role=payload.role or "member",
        )
    )
    db.commit()
    # Webhook
    try:
        from app.services.webhook_service import emit_event

        emit_event(
            db,
            project_id=project_id,
            event="member.joined",
            data={
                "text": f"👋 {target.name} joined the project",
                "user_id": target.id,
                "name": target.name,
                "email": target.email,
                "added_by": current.id,
            },
        )
    except Exception:
        pass
    return {"status": "added", "user_id": target.id}


@router.get("/{project_id}/activity", response_model=ActivityHeatmapOut)
def activity_heatmap(
    project_id: str,
    weeks: int = 12,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActivityHeatmapOut:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pm = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current.id,
        )
        .first()
    )
    if not pm:
        raise HTTPException(status_code=403, detail="Not a project member")

    cells, total, per_user = build_activity_heatmap(db, project_id, weeks=weeks)
    return ActivityHeatmapOut(
        weeks=weeks,
        cells=[ActivityCell(**c) for c in cells],
        total=total,
        per_user=per_user,
    )
