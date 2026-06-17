"""AI reports router - generates an advisor report for a project."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.meeting import AIReport, ExtractedTask, Meeting
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskHistory
from app.rate_limit import limiter
from app.models.user import User
from app.schemas.ai import AIReportOut
from pydantic import BaseModel


class ApproveExtractedOut(BaseModel):
    taskId: str
    status: str
from app.services.auth_service import get_current_user
from app.services.cpm_service import CPMTaskInput, calculate_cpm
from app.services.contribution_service import (
    MemberTaskStats,
    calculate_contribution,
)
from app.services.realtime import broadcast_sync


logger = logging.getLogger(__name__)
router = APIRouter(prefix=f"{settings.API_PREFIX}", tags=["ai"])


def _ensure_member(db: Session, project_id: str, user_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pm = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        .first()
    )
    if not pm:
        raise HTTPException(status_code=403, detail="Not a project member")
    return project


def _build_project_data(db: Session, project: Project) -> Dict[str, Any]:
    tasks = db.query(Task).filter(Task.project_id == project.id).all()
    completed = [t for t in tasks if t.status == "done"]
    now = datetime.now(tz=timezone.utc)
    overdue = 0
    for t in tasks:
        if t.deadline and t.status != "done":
            dl = t.deadline if t.deadline.tzinfo else t.deadline.replace(tzinfo=timezone.utc)
            if dl < now:
                overdue += 1

    members = (
        db.query(User)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .filter(ProjectMember.project_id == project.id)
        .all()
    )
    histories = (
        db.query(TaskHistory)
        .join(Task, Task.id == TaskHistory.task_id)
        .filter(Task.project_id == project.id)
        .all()
    )

    stats: List[MemberTaskStats] = []
    for u in members:
        ut = [t for t in tasks if t.assignee_id == u.id]
        uc = [t for t in ut if t.status == "done"]
        on_time = 0
        for t in uc:
            if t.deadline and t.completed_at:
                dl = t.deadline if t.deadline.tzinfo else t.deadline.replace(tzinfo=timezone.utc)
                ca = t.completed_at if t.completed_at.tzinfo else t.completed_at.replace(tzinfo=timezone.utc)
                if ca <= dl:
                    on_time += 1
        uh = [h for h in histories if h.user_id == u.id]
        last = max(
            ([h.created_at for h in uh] + [t.created_at for t in ut]),
            default=None,
        )
        stats.append(
            MemberTaskStats(
                user_id=u.id,
                tasks_completed=len(uc),
                tasks_assigned=len(ut),
                story_points_completed=sum(t.story_points for t in uc),
                story_points_assigned=sum(t.story_points for t in ut),
                on_time_completed=on_time,
                activity_count=len(uh),
                last_activity=last,
            )
        )
    results = calculate_contribution(stats)
    by_id = {r.user_id: r for r in results}

    member_payload = []
    for u in members:
        r = by_id.get(u.id)
        if not r:
            continue
        member_payload.append(
            {
                "name": u.name,
                "contribution_score": r.score,
                "contribution_percent": r.percent,
                "tasks_completed": r.breakdown.get("tasks_completed", 0),
                "tasks_assigned": r.breakdown.get("tasks_assigned", 0),
                "story_points_completed": r.breakdown.get("story_points_completed", 0),
                "on_time_rate": r.breakdown.get("on_time_rate", 0.0),
                "last_activity_days_ago": r.last_activity_days_ago,
                "is_ghost": r.is_ghost,
            }
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
    critical = [
        {
            "id": t.id,
            "title": t.title,
            "early_finish": t.early_finish,
            "slack": t.slack,
        }
        for t in cpm.tasks
        if t.is_critical
    ]

    days_remaining: int = 0
    if project.deadline:
        dl = project.deadline if project.deadline.tzinfo else project.deadline.replace(tzinfo=timezone.utc)
        days_remaining = max(0, (dl - now).days)
    return {
        "project_title": project.title,
        "deadline": project.deadline.isoformat() if project.deadline else None,
        "days_remaining": days_remaining,
        "total_tasks": len(tasks),
        "completed_tasks": len(completed),
        "overdue_tasks": overdue,
        "delay_risk": cpm.delay_risk,
        "critical_path_tasks": critical,
        "members": member_payload,
    }


@router.post(
    "/projects/{project_id}/reports/generate",
    response_model=AIReportOut,
    status_code=201,
)
@limiter.limit(settings.RATE_LIMIT_AI)
async def generate_report(
    request: Request,
    project_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIReportOut:
    project = _ensure_member(db, project_id, current.id)
    data = _build_project_data(db, project)
    from app.services.ai_advisor import generate_project_report

    text = await generate_project_report(data)
    report = AIReport(
        project_id=project_id,
        report_text=text,
        contribution_snapshot={"members": data["members"]},
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    broadcast_sync(
        project_id,
        {"type": "report.generated", "reportId": report.id},
    )
    return AIReportOut.model_validate(report)


@router.get(
    "/projects/{project_id}/reports", response_model=List[AIReportOut]
)
def list_reports(
    project_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[AIReportOut]:
    _ensure_member(db, project_id, current.id)
    rows = (
        db.query(AIReport)
        .filter(AIReport.project_id == project_id)
        .order_by(AIReport.created_at.desc())
        .all()
    )
    return [AIReportOut.model_validate(r) for r in rows]


@router.get("/reports/{report_id}", response_model=AIReportOut)
def get_report(
    report_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIReportOut:
    report = db.query(AIReport).filter(AIReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    _ensure_member(db, report.project_id, current.id)
    return AIReportOut.model_validate(report)


@router.post(
    "/extracted-tasks/{extracted_id}/approve",
    response_model=ApproveExtractedOut,
)
async def approve_extracted_task(
    extracted_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Approve an extracted task and import it into the project as a Task."""
    row = db.query(ExtractedTask).filter(ExtractedTask.id == extracted_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Extracted task not found")
    meeting = db.query(Meeting).filter(Meeting.id == row.meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    _ensure_member(db, meeting.project_id, current.id)

    data = row.task_data or {}
    task = Task(
        project_id=meeting.project_id,
        title=str(data.get("title", "Untitled"))[:500],
        description=data.get("description"),
        assignee_id=data.get("assignee_id"),
        story_points=int(data.get("story_points") or 1),
        status="todo",
    )
    task.depends_on = []
    db.add(task)
    db.flush()
    row.is_approved = True
    row.approved_by = current.id
    row.imported_task_id = task.id
    db.commit()
    broadcast_sync(
        meeting.project_id,
        {
            "type": "task.imported",
            "taskId": task.id,
            "source": "ai_extracted",
        },
    )
    return {"taskId": task.id, "status": "imported"}


@router.post("/extracted-tasks/{extracted_id}/reject", status_code=204)
def reject_extracted_task(
    extracted_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    row = db.query(ExtractedTask).filter(ExtractedTask.id == extracted_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Extracted task not found")
    meeting = db.query(Meeting).filter(Meeting.id == row.meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    _ensure_member(db, meeting.project_id, current.id)
    db.delete(row)
    db.commit()
