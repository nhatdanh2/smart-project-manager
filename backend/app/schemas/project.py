"""Pydantic schemas for projects and members."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.user import UserOut


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    deadline: datetime
    instructor_id: Optional[str] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    status: Optional[str] = None


class MemberAdd(BaseModel):
    user_id: str
    role: str = "member"


class MemberOut(BaseModel):
    user_id: str
    name: str
    email: str
    role: str
    contribution_percent: Optional[float] = None

    class Config:
        from_attributes = True


class ProjectOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    deadline: datetime
    status: str
    instructor_id: Optional[str] = None
    created_at: datetime
    members: List[MemberOut] = []

    class Config:
        from_attributes = True


class ProjectSummary(BaseModel):
    """Return value for /projects/{id}/summary."""
    project: ProjectOut
    total_tasks: int
    completed_tasks: int
    overdue_tasks: int
    cpm_project_duration: Optional[int] = None
    cpm_estimated_completion: Optional[datetime] = None
    cpm_delay_risk: Optional[float] = None
    cpm_critical_path: List[str] = []
