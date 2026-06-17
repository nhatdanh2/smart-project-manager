"""Pydantic schemas for AI features: meetings, extracted tasks, reports."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MeetingOut(BaseModel):
    id: str
    project_id: str
    title: Optional[str] = None
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    status: str
    transcript: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ExtractedTaskOut(BaseModel):
    id: str
    meeting_id: str
    task_data: Dict[str, Any]
    is_approved: bool
    imported_task_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ExtractedTaskApprove(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    story_points: Optional[int] = Field(default=None, ge=1, le=13)
    deadline: Optional[datetime] = None
    depends_on: List[str] = []


class AIReportOut(BaseModel):
    id: str
    project_id: str
    report_text: str
    contribution_snapshot: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True
