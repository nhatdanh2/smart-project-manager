"""Projects router: list, create, retrieve, update, delete, members, summary."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models.contribution import ContributionScore
from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.user import User
from app.schemas.project import (
    MemberAdd,
    MemberOut,
    ProjectCreate,
    ProjectOut,
    ProjectSummary,
    ProjectUpdate,
)
from app.services.auth_service import get_current_user
from app.services.cpm_service import CPMTaskInput, calculate_cpm
from app.services.realtime import broadcast_sync


logger = logging.getLogger(__name__)
router = APIRouter(prefix=f"{settings.API_PREFIX}/projects", tags=["projects"])


def _ensure_member(db: Session, project: Project, user_id: str) -> None:
    member = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project.id, ProjectMember.user_id == user_id
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=403, detail="You are not a member of this project")


def _build_member_out(db: Session, project: Project) -> List[MemberOut]:
    rows = (
        db.query(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .filter(ProjectMember.project_id == project.id)
        .all()
    )
    # attach latest contribution percent from cached rows
    latest_scores: dict[str, float] = {}
    if rows:
        member_ids = [u.id for _, u in rows]
        for cs in (
            db.query(ContributionScore)
            .filter(
                ContributionScore.project_id == project.id,
                ContributionScore.user_id.in_(member_ids),
            )
            .all()
        ):
            # The cell ``contribution_percent`` should be 0..100.  We
            # prefer the value inside ``breakdown`` (set by
            # ``calculate_all_contributions``); fall back to the raw
            # ``score`` field if breakdown is missing for some reason.
            percent: Optional[float] = None
            if cs.breakdown and "percent" in cs.breakdown:
                percent = float(cs.breakdown["percent"])
            elif cs.breakdown and "story_points_completed" in cs.breakdown:
                # No percent stored — recompute roughly from the
                # breakdowns (score is the raw weighted score ~0..1).
                # In practice calculate_all_contributions always stores
                # a ``percent`` key, so this branch is a safety net.
                percent = round(float(cs.score) * 100, 2)
            latest_scores[cs.user_id] = percent if percent is not None else float(cs.score) * 100
    out: List[MemberOut] = []
    for pm, user in rows:
        out.append(
            MemberOut(
                user_id=user.id,
                name=user.name,
                email=user.email,
                role=pm.role,
                contribution_percent=latest_scores.get(user.id),
            )
        )
    return out


def _project_to_out(db: Session, project: Project) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        title=project.title,
        description=project.description,
        deadline=project.deadline,
        status=project.status,
        instructor_id=project.instructor_id,
        created_at=project.created_at,
        members=_build_member_out(db, project),
    )


@router.get("", response_model=List[ProjectOut])
def list_projects(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> List[ProjectOut]:
    rows = (
        db.query(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .filter(ProjectMember.user_id == current.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    return [_project_to_out(db, p) for p in rows]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOut:
    project = Project(
        title=payload.title.strip(),
        description=payload.description,
        deadline=payload.deadline,
        instructor_id=payload.instructor_id,
    )
    db.add(project)
    db.flush()
    db.add(
        ProjectMember(project_id=project.id, user_id=current.id, role="leader")
    )
    db.commit()
    db.refresh(project)
    return _project_to_out(db, project)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOut:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _ensure_member(db, project, current.id)
    return _project_to_out(db, project)


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOut:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _ensure_member(db, project, current.id)
    if payload.title is not None:
        project.title = payload.title.strip()
    if payload.description is not None:
        project.description = payload.description
    if payload.deadline is not None:
        project.deadline = payload.deadline
    if payload.status is not None:
        project.status = payload.status
    db.commit()
    db.refresh(project)
    return _project_to_out(db, project)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    # only leader or instructor
    pm = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current.id,
            ProjectMember.role == "leader",
        )
        .first()
    )
    if not pm and current.role not in ("instructor", "admin"):
        raise HTTPException(status_code=403, detail="Only the project leader can delete")
    db.delete(project)
    db.commit()


@router.post("/{project_id}/members", response_model=ProjectOut)
def add_member(
    project_id: str,
    payload: MemberAdd,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOut:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _ensure_member(db, project, current.id)

    target = db.query(User).filter(User.id == payload.user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == payload.user_id,
        )
        .first()
    )
    if existing:
        existing.role = payload.role
    else:
        db.add(
            ProjectMember(
                project_id=project_id,
                user_id=payload.user_id,
                role=payload.role,
            )
        )
    db.commit()
    db.refresh(project)
    if not existing:
        from app.services.notification_service import notify

        notify(
            db,
            user_id=payload.user_id,
            type="member.added",
            title=f"Bạn được thêm vào: {project.title}",
            body=f"{current.name} đã thêm bạn vào dự án với vai trò {payload.role}.",
            link=f"/projects/{project_id}",
            project_id=project_id,
        )
    broadcast_sync(project_id, {"type": "member.joined", "user": {"id": target.id, "name": target.name}})
    return _project_to_out(db, project)


@router.delete("/{project_id}/members/{user_id}", response_model=ProjectOut)
def remove_member(
    project_id: str,
    user_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOut:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _ensure_member(db, project, current.id)

    pm = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        .first()
    )
    if not pm:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(pm)
    db.commit()
    db.refresh(project)
    return _project_to_out(db, project)


@router.get("/{project_id}/summary", response_model=ProjectSummary)
def project_summary(
    project_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectSummary:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _ensure_member(db, project, current.id)

    tasks = db.query(Task).filter(Task.project_id == project_id).all()
    completed = sum(1 for t in tasks if t.status == "done")
    now = datetime.now(tz=timezone.utc)
    overdue = sum(
        1
        for t in tasks
        if t.deadline is not None
        and t.status != "done"
        and (t.deadline if t.deadline.tzinfo else t.deadline.replace(tzinfo=timezone.utc)) < now
    )

    cpm = calculate_cpm(
        tasks=[
            CPMTaskInput(
                id=t.id,
                title=t.title,
                story_points=t.story_points,
                depends_on=t.depends_on,
            )
            for t in tasks
        ],
        deadline=project.deadline,
    )

    return ProjectSummary(
        project=_project_to_out(db, project),
        total_tasks=len(tasks),
        completed_tasks=completed,
        overdue_tasks=overdue,
        cpm_project_duration=cpm.project_duration,
        cpm_estimated_completion=cpm.estimated_completion,
        cpm_delay_risk=cpm.delay_risk,
        cpm_critical_path=cpm.critical_path,
    )
