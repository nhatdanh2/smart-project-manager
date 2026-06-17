"""Tasks router: list/create/update/delete/move + CPM recalc."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskHistory
from app.models.user import User
from app.schemas.task import (
    CPMResultOut,
    TaskCreate,
    TaskMove,
    TaskOut,
    TaskUpdate,
)
from app.schemas.user import AuditEntryOut, BulkTaskUpdate, CommentCreate, CommentOut
from app.services.auth_service import get_current_user
from app.services.cpm_service import CPMTaskInput, calculate_cpm
from app.services.realtime import broadcast_sync


logger = logging.getLogger(__name__)
router = APIRouter(prefix=f"{settings.API_PREFIX}", tags=["tasks"])


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


def _serialize_task(db: Session, task: Task) -> TaskOut:
    assignee_name: Optional[str] = None
    if task.assignee_id:
        u = db.query(User).filter(User.id == task.assignee_id).first()
        if u:
            assignee_name = u.name
    is_overdue = False
    if task.deadline and task.status != "done":
        dl = task.deadline if task.deadline.tzinfo else task.deadline.replace(tzinfo=timezone.utc)
        is_overdue = dl < datetime.now(tz=timezone.utc)
    return TaskOut(
        id=task.id,
        project_id=task.project_id,
        assignee_id=task.assignee_id,
        assignee_name=assignee_name,
        title=task.title,
        description=task.description,
        status=task.status,
        story_points=task.story_points,
        priority=getattr(task, "priority", 100) or 100,
        deadline=task.deadline,
        completed_at=task.completed_at,
        depends_on=task.depends_on,
        early_start=task.early_start,
        early_finish=task.early_finish,
        late_start=task.late_start,
        late_finish=task.late_finish,
        slack=task.slack,
        is_critical=task.is_critical,
        is_overdue=is_overdue,
        recurrence=getattr(task, "recurrence", None),
        parent_task_id=getattr(task, "parent_task_id", None),
        created_at=task.created_at,
    )


def _persist_cpm(db: Session, project_id: str) -> None:
    tasks = db.query(Task).filter(Task.project_id == project_id).all()
    cpm = calculate_cpm(
        tasks=[
            CPMTaskInput(
                id=t.id,
                title=t.title,
                story_points=t.story_points,
                depends_on=t.depends_on,
            )
            for t in tasks
        ]
    )
    by_id = {r.id: r for r in cpm.tasks}
    for t in tasks:
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


def _project_title(db: Session, project_id: str) -> str:
    from app.models.project import Project

    row = db.query(Project).filter(Project.id == project_id).first()
    return row.title if row else ""


@router.get("/projects/{project_id}/tasks", response_model=List[TaskOut])
def list_tasks(
    project_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[TaskOut]:
    _ensure_member(db, project_id, current.id)
    tasks = (
        db.query(Task)
        .filter(Task.project_id == project_id)
        .order_by(Task.status.asc(), Task.priority.asc(), Task.created_at.asc())
        .all()
    )
    return [_serialize_task(db, t) for t in tasks]


@router.post("/projects/{project_id}/tasks", response_model=TaskOut, status_code=201)
def create_task(
    project_id: str,
    payload: TaskCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskOut:
    _ensure_member(db, project_id, current.id)
    # Default priority: append to the end of its column
    max_priority_row = (
        db.query(Task)
        .filter(Task.project_id == project_id, Task.status == (payload.status or "todo"))
        .order_by(Task.priority.desc())
        .first()
    )
    next_priority = (max_priority_row.priority + 10) if max_priority_row else 10
    task = Task(
        project_id=project_id,
        assignee_id=payload.assignee_id,
        title=payload.title.strip(),
        description=payload.description,
        status=payload.status or "todo",
        story_points=payload.story_points or 1,
        priority=next_priority,
        deadline=payload.deadline,
        recurrence=payload.recurrence if payload.recurrence != "none" else None,
        parent_task_id=None,
    )
    task.depends_on = payload.depends_on or []
    db.add(task)
    db.flush()
    db.add(
        TaskHistory(
            task_id=task.id,
            user_id=current.id,
            action="created",
            new_value=task.status,
        )
    )
    db.commit()
    db.refresh(task)
    _persist_cpm(db, project_id)
    # Index for search (Meilisearch).  Best effort — never blocks the
    # response.
    try:
        from app.services.search_service import index_task

        index_task(
            {
                "id": task.id,
                "project_id": task.project_id,
                "title": task.title,
                "description": task.description or "",
                "status": task.status,
                "assignee_id": task.assignee_id or "",
                "project_title": _project_title(db, project_id),
                "created_at": int(task.created_at.timestamp()) if task.created_at else 0,
                "deadline": int(task.deadline.timestamp()) if task.deadline else 0,
            }
        )
    except Exception:
        pass
    broadcast_sync(
        project_id,
        {"type": "task.created", "task": json_compat(_serialize_task(db, task).model_dump())},
    )
    # Notify the assignee (if any) - skip the creator
    if task.assignee_id and task.assignee_id != current.id:
        from app.services.notification_service import notify

        notify(
            db,
            user_id=task.assignee_id,
            type="task.assigned",
            title=f"Task mới: {task.title}",
            body=f"{current.name} đã giao task cho bạn trong dự án.",
            link=f"/projects/{project_id}/kanban",
            project_id=project_id,
        )
    # Webhook
    try:
        from app.services.webhook_service import emit_event

        emit_event(
            db,
            project_id=project_id,
            event="task.created",
            data={
                "text": f"New task: {task.title}",
                "task_id": task.id,
                "title": task.title,
                "status": task.status,
                "assignee_id": task.assignee_id,
                "created_by": current.id,
            },
        )
    except Exception:
        pass
    return _serialize_task(db, task)


@router.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskOut:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    _ensure_member(db, task.project_id, current.id)

    changes: List[dict] = []
    if payload.title is not None and payload.title != task.title:
        changes.append({"field": "title", "old": task.title, "new": payload.title})
        task.title = payload.title.strip()
    if payload.description is not None and payload.description != task.description:
        task.description = payload.description
    if payload.assignee_id is not None:
        changes.append({"field": "assignee", "old": task.assignee_id, "new": payload.assignee_id})
        task.assignee_id = payload.assignee_id
    if payload.status is not None and payload.status != task.status:
        changes.append({"field": "status", "old": task.status, "new": payload.status})
        task.status = payload.status
        if payload.status == "done" and not task.completed_at:
            task.completed_at = datetime.now(tz=timezone.utc)
        if payload.status != "done":
            task.completed_at = None
    if payload.story_points is not None:
        task.story_points = payload.story_points
    if payload.deadline is not None:
        task.deadline = payload.deadline
    if payload.depends_on is not None:
        task.depends_on = payload.depends_on
    if payload.recurrence is not None:
        new_rec = payload.recurrence if payload.recurrence != "none" else None
        if new_rec != task.recurrence:
            changes.append(
                {"field": "recurrence", "old": task.recurrence or "none", "new": new_rec or "none"}
            )
            task.recurrence = new_rec

    for c in changes:
        db.add(
            TaskHistory(
                task_id=task.id,
                user_id=current.id,
                action=f"{c['field']}_changed",
                old_value=str(c["old"]),
                new_value=str(c["new"]),
            )
        )

    db.commit()
    db.refresh(task)
    _persist_cpm(db, task.project_id)
    broadcast_sync(
        task.project_id,
        {
            "type": "task.updated",
            "taskId": task.id,
            "changes": changes,
        },
    )
    return _serialize_task(db, task)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    _ensure_member(db, task.project_id, current.id)
    project_id = task.project_id
    db.delete(task)
    db.commit()
    _persist_cpm(db, project_id)


@router.put("/tasks/{task_id}/move", response_model=TaskOut)
def move_task(
    task_id: str,
    payload: TaskMove,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskOut:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    _ensure_member(db, task.project_id, current.id)
    if payload.status not in ("todo", "in_progress", "review", "done"):
        raise HTTPException(status_code=400, detail="Invalid status")
    old_status = task.status
    task.status = payload.status
    if payload.status == "done" and not task.completed_at:
        task.completed_at = datetime.now(tz=timezone.utc)
    if payload.status != "done":
        task.completed_at = None

    # Reorder inside the target column.
    # We renumber `priority` for every task in the same status (old or new)
    # so positions stay consistent.  If a `position` is provided we splice
    # the moved task in at that index.
    target_status = payload.status
    siblings = (
        db.query(Task)
        .filter(Task.project_id == task.project_id, Task.status == target_status)
        .order_by(Task.priority.asc(), Task.created_at.asc())
        .all()
    )
    if payload.position is not None and target_status == old_status:
        # Reorder within same column
        siblings = [s for s in siblings if s.id != task.id]
        pos = max(0, min(payload.position, len(siblings)))
        siblings.insert(pos, task)
        for idx, sibling in enumerate(siblings):
            sibling.priority = (idx + 1) * 10
    elif payload.position is not None and target_status != old_status:
        # Move to a new column at a specific position
        siblings = [s for s in siblings if s.id != task.id]
        pos = max(0, min(payload.position, len(siblings)))
        siblings.insert(pos, task)
        for idx, sibling in enumerate(siblings):
            sibling.priority = (idx + 1) * 10
        # Also renumber the old column to keep it tidy
        old_siblings = (
            db.query(Task)
            .filter(
                Task.project_id == task.project_id,
                Task.status == old_status,
                Task.id != task.id,
            )
            .order_by(Task.priority.asc(), Task.created_at.asc())
            .all()
        )
        for idx, sibling in enumerate(old_siblings):
            sibling.priority = (idx + 1) * 10
    else:
        # No explicit position - just bump to top/bottom of new column
        if target_status != old_status:
            max_priority = max(
                (s.priority for s in siblings if s.id != task.id),
                default=0,
            )
            task.priority = max_priority + 10

    db.add(
        TaskHistory(
            task_id=task.id,
            user_id=current.id,
            action="status_changed",
            old_value=old_status,
            new_value=payload.status,
        )
    )
    db.commit()
    db.refresh(task)
    broadcast_sync(
        task.project_id,
        {
            "type": "task.moved",
            "taskId": task.id,
            "fromStatus": old_status,
            "toStatus": payload.status,
            "movedBy": current.id,
            "position": payload.position,
        },
    )
    # Recurring tasks: spawn next occurrence when moved to done
    if payload.status == "done" and old_status != "done":
        from app.services.recurrence_service import spawn_next_occurrence

        next_task = spawn_next_occurrence(db, task)
        if next_task:
            broadcast_sync(
                task.project_id,
                {
                    "type": "task.spawned",
                    "parentId": task.id,
                    "task": {"id": next_task.id, "title": next_task.title},
                },
            )
    # Notify assignee & leader when status hits "done"
    if payload.status == "done" and old_status != "done":
        from app.models.project import ProjectMember
        from app.services.notification_service import notify

        # Leader(s)
        leaders = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == task.project_id,
                ProjectMember.role == "leader",
            )
            .all()
        )
        for leader in leaders:
            if leader.user_id == current.id:
                continue
            notify(
                db,
                user_id=leader.user_id,
                type="task.done",
                title=f"✅ Hoàn thành: {task.title}",
                body=f"{current.name} vừa đánh dấu task hoàn thành.",
                link=f"/projects/{task.project_id}/kanban",
                project_id=task.project_id,
            )
    # Webhooks
    try:
        from app.services.webhook_service import emit_event

        emit_event(
            db,
            project_id=task.project_id,
            event="task.moved",
            data={
                "text": f"Task moved: {task.title} → {payload.status}",
                "task_id": task.id,
                "title": task.title,
                "from_status": old_status,
                "to_status": payload.status,
                "moved_by": current.id,
            },
        )
        if payload.status == "done" and old_status != "done":
            emit_event(
                db,
                project_id=task.project_id,
                event="task.completed",
                data={
                    "text": f"✅ Done: {task.title}",
                    "task_id": task.id,
                    "title": task.title,
                    "completed_by": current.id,
                },
            )
    except Exception:
        pass

    # ----------------------------------------------------------------
    # Trigger downstream recomputes
    # ----------------------------------------------------------------
    # Always re-run CPM (a column move can break/extend the critical
    # path).  Try Celery first, fall back to inline so dev installs
    # without a worker still see the result.
    try:
        from app.workers.tasks import recalculate_cpm

        recalculate_cpm.delay(task.project_id)
    except Exception:
        try:
            # Run synchronously (in-process) — captures the result so
            # the next WS broadcast includes the new critical path.
            from app.services.cpm_service import calculate_cpm, CPMTaskInput
            tasks_q = db.query(Task).filter(Task.project_id == task.project_id).all()
            cpm = calculate_cpm(
                tasks=[
                    CPMTaskInput(
                        id=t.id, title=t.title, story_points=t.story_points or 1,
                        depends_on=t.depends_on or [],
                    )
                    for t in tasks_q
                ]
            )
            broadcast_sync(
                task.project_id,
                {
                    "type": "cpm.recalculated",
                    "criticalPath": cpm.critical_path,
                    "projectDuration": cpm.project_duration,
                    "delayRisk": cpm.delay_risk,
                },
            )
        except Exception:
            pass

    # Re-calc contribution only when a task *enters* done, since
    # those scores are derived from done-task points / activity.
    if payload.status == "done" and old_status != "done":
        try:
            from app.workers.tasks import calculate_all_contributions

            calculate_all_contributions.delay(task.project_id)
        except Exception:
            # Best effort — if worker is down the next scheduled
            # search_reindex_job or a manual trigger will pick it up.
            pass
    return _serialize_task(db, task)


@router.post("/projects/{project_id}/tasks/bulk", response_model=dict)
def bulk_update_tasks(
    project_id: str,
    payload: BulkTaskUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Batch update tasks - used by multi-select toolbar in Kanban.

    - Status / assignee changes are applied to every task in the list.
    - If ``delete`` is true, every task is deleted (cascading).
    The endpoint returns counts for the UI to display a summary toast.
    """
    _ensure_member(db, project_id, current.id)
    tasks = (
        db.query(Task)
        .filter(Task.project_id == project_id, Task.id.in_(payload.task_ids))
        .all()
    )
    if not tasks:
        raise HTTPException(status_code=404, detail="No tasks matched")

    if payload.delete:
        ids = [t.id for t in tasks]
        # TaskHistory rows cascade with task
        for t in tasks:
            db.add(
                TaskHistory(
                    task_id=t.id,
                    user_id=current.id,
                    action="bulk_deleted",
                )
            )
        db.query(Task).filter(Task.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        broadcast_sync(
            project_id,
            {"type": "task.bulk_deleted", "taskIds": ids, "by": current.id},
        )
        return {"deleted": len(ids)}

    updated = 0
    for t in tasks:
        changed = False
        if payload.status and payload.status != t.status:
            old = t.status
            t.status = payload.status
            if payload.status == "done" and not t.completed_at:
                t.completed_at = datetime.now(tz=timezone.utc)
            if payload.status != "done":
                t.completed_at = None
            db.add(
                TaskHistory(
                    task_id=t.id,
                    user_id=current.id,
                    action="bulk_status_changed",
                    old_value=old,
                    new_value=payload.status,
                )
            )
            changed = True
        if (
            payload.assignee_id is not None
            and payload.assignee_id != t.assignee_id
        ):
            old = t.assignee_id
            t.assignee_id = payload.assignee_id or None
            db.add(
                TaskHistory(
                    task_id=t.id,
                    user_id=current.id,
                    action="bulk_assignee_changed",
                    old_value=old or "",
                    new_value=t.assignee_id or "",
                )
            )
            changed = True
        if changed:
            updated += 1
    db.commit()
    if updated:
        broadcast_sync(
            project_id,
            {
                "type": "task.bulk_updated",
                "taskIds": payload.task_ids,
                "status": payload.status,
                "assigneeId": payload.assignee_id,
                "by": current.id,
            },
        )
    return {"updated": updated, "total": len(tasks)}


@router.get("/tasks/{task_id}/comments", response_model=List[CommentOut])
def list_comments(
    task_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[CommentOut]:
    from app.models.comment import TaskComment

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    _ensure_member(db, task.project_id, current.id)
    rows = (
        db.query(TaskComment)
        .filter(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.asc())
        .all()
    )
    user_ids = list({r.user_id for r in rows})
    from app.models.user import User as UserModel

    users = (
        db.query(UserModel).filter(UserModel.id.in_(user_ids)).all() if user_ids else []
    )
    name_by_id = {u.id: u.name for u in users}
    out: List[CommentOut] = []
    for r in rows:
        out.append(
            CommentOut(
                id=r.id,
                task_id=r.task_id,
                user_id=r.user_id,
                user_name=name_by_id.get(r.user_id),
                body=r.body,
                mentions=r.mentions,
                created_at=r.created_at,
            )
        )
    return out


@router.post("/tasks/{task_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    task_id: str,
    payload: CommentCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentOut:
    from app.models.comment import TaskComment

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    _ensure_member(db, task.project_id, current.id)
    import json

    mentions = payload.mentions or []
    comment = TaskComment(
        task_id=task_id,
        user_id=current.id,
        body=payload.body.strip(),
        mentions_json=json.dumps(mentions) if mentions else None,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    broadcast_sync(
        task.project_id,
        {
            "type": "comment.added",
            "taskId": task_id,
            "commentId": comment.id,
            "userId": current.id,
        },
    )
    # Notify mentions (and task assignee if not the commenter)
    from app.services.notification_service import notify

    for uid in mentions:
        if uid == current.id:
            continue
        notify(
            db,
            user_id=uid,
            type="mention",
            title=f"💬 {current.name} nhắc đến bạn",
            body=f"Trong task: {task.title}",
            link=f"/projects/{task.project_id}/kanban",
            project_id=task.project_id,
        )
    if task.assignee_id and task.assignee_id not in mentions and task.assignee_id != current.id:
        notify(
            db,
            user_id=task.assignee_id,
            type="comment.added",
            title=f"💬 Bình luận mới trên: {task.title}",
            body=f"{current.name}: {payload.body[:80]}",
            link=f"/projects/{task.project_id}/kanban",
            project_id=task.project_id,
        )
    return CommentOut(
        id=comment.id,
        task_id=comment.task_id,
        user_id=comment.user_id,
        user_name=current.name,
        body=comment.body,
        mentions=comment.mentions,
        created_at=comment.created_at,
    )


@router.get("/tasks/{task_id}/audit", response_model=List[AuditEntryOut])
def task_audit_log(
    task_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[AuditEntryOut]:

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    _ensure_member(db, task.project_id, current.id)
    rows = (
        db.query(TaskHistory)
        .filter(TaskHistory.task_id == task_id)
        .order_by(TaskHistory.created_at.desc())
        .limit(200)
        .all()
    )
    user_ids = {r.user_id for r in rows if r.user_id}
    from app.models.user import User as UserModel

    users = (
        db.query(UserModel).filter(UserModel.id.in_(user_ids)).all()
        if user_ids
        else []
    )
    name_by_id = {u.id: u.name for u in users}
    out: List[AuditEntryOut] = []
    for r in rows:
        out.append(
            AuditEntryOut(
                id=r.id,
                task_id=r.task_id,
                user_id=r.user_id,
                user_name=name_by_id.get(r.user_id) if r.user_id else None,
                action=r.action,
                old_value=r.old_value,
                new_value=r.new_value,
                created_at=r.created_at,
            )
        )
    return out


@router.post("/projects/{project_id}/cpm/recalculate", response_model=CPMResultOut)
def recalculate_cpm(
    project_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CPMResultOut:
    _ensure_member(db, project_id, current.id)
    tasks = db.query(Task).filter(Task.project_id == project_id).all()
    project = db.query(Project).filter(Project.id == project_id).first()
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
        deadline=project.deadline if project else None,
    )
    by_id = {r.id: r for r in cpm.tasks}
    for t in tasks:
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
    return CPMResultOut(
        project_duration=cpm.project_duration,
        estimated_completion=cpm.estimated_completion,
        delay_risk=cpm.delay_risk,
        critical_path=cpm.critical_path,
        tasks=[_serialize_task(db, t) for t in tasks],
    )


def json_compat(obj):
    """Convert datetime fields in a dict to ISO strings (used for WS payloads)."""
    from datetime import date, datetime
    import json

    def _conv(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, dict):
            return {k: _conv(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_conv(v) for v in o]
        return o

    return _conv(obj)


@router.get("/projects/{project_id}/search")
def search_project(
    project_id: str,
    q: str = Query("", description="Search query"),
    index: str = Query("tasks", regex="^(tasks|meetings)$"),
    status_filter: Optional[str] = Query(None, alias="status"),
    assignee_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Full-text search powered by Meilisearch (with safe Postgres fallback)."""
    _ensure_member(db, project_id, current.id)
    from app.services.search_service import search as meili_search, is_enabled

    if not is_enabled():
        # Fall back to an ILIKE scan — fine while dataset is small.
        from sqlalchemy import or_

        q_like = f"%{q}%"
        if index == "tasks":
            rows = (
                db.query(Task)
                .filter(
                    Task.project_id == project_id,
                    or_(Task.title.ilike(q_like), Task.description.ilike(q_like)),
                )
                .order_by(Task.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            return {
                "hits": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "status": t.status,
                        "project_id": t.project_id,
                    }
                    for t in rows
                ],
                "estimatedTotalHits": len(rows),
                "backend": "postgres-fallback",
            }
        # meetings
        from app.models.meeting import Meeting

        rows = (
            db.query(Meeting)
            .filter(
                Meeting.project_id == project_id,
                or_(Meeting.title.ilike(q_like), Meeting.transcript.ilike(q_like)),
            )
            .order_by(Meeting.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return {
            "hits": [
                {
                    "id": m.id,
                    "title": m.title,
                    "status": m.status,
                    "project_id": m.project_id,
                }
                for m in rows
            ],
            "estimatedTotalHits": len(rows),
            "backend": "postgres-fallback",
        }

    extra = []
    if status_filter:
        extra.append(f'status = "{status_filter}"')
    if assignee_id:
        extra.append(f'assignee_id = "{assignee_id}"')
    result = meili_search(
        q,
        index=index,
        project_id=project_id,
        extra_filters=extra,
        limit=limit,
        offset=offset,
    )
    result["backend"] = "meilisearch"
    return result
