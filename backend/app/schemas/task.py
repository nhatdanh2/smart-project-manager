"""Pydantic schemas for tasks."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    status: str = "todo"
    story_points: int = Field(default=1, ge=1, le=13)
    deadline: Optional[datetime] = None
    depends_on: List[str] = []
    recurrence: Optional[str] = None  # "none" | "daily" | "weekly" | "biweekly" | "monthly"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    status: Optional[str] = None
    story_points: Optional[int] = Field(default=None, ge=1, le=13)
    priority: Optional[int] = None
    deadline: Optional[datetime] = None
    depends_on: Optional[List[str]] = None
    recurrence: Optional[str] = None


class TaskMove(BaseModel):
    """Used by Kanban drag & drop."""
    status: str
    # Position inside the target column (0-based).  Lower = top.
    position: Optional[int] = None


class CPMFields(BaseModel):
    early_start: Optional[int] = None
    early_finish: Optional[int] = None
    late_start: Optional[int] = None
    late_finish: Optional[int] = None
    slack: Optional[int] = None
    is_critical: bool = False


class CPMTaskInput(BaseModel):
    """Single task as fed into the CPM calculator."""
    id: str
    title: str = ""
    story_points: int = 1
    status: str = "todo"
    depends_on: List[str] = []


class TaskOut(BaseModel):
    id: str
    project_id: str
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: str
    story_points: int
    deadline: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    depends_on: List[str] = []
    early_start: Optional[int] = None
    early_finish: Optional[int] = None
    late_start: Optional[int] = None
    late_finish: Optional[int] = None
    slack: Optional[int] = None
    is_critical: bool = False
    is_overdue: bool = False
    priority: int = 100
    recurrence: Optional[str] = None
    parent_task_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CPMResultOut(BaseModel):
    project_duration: int
    estimated_completion: Optional[datetime] = None
    delay_risk: float
    critical_path: List[str]
    tasks: List[TaskOut]
