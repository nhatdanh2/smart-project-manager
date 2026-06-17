"""Pydantic schemas for users and authentication."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    name: str


class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=128)
    role: Optional[str] = "student"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(UserBase):
    id: str
    role: str
    avatar_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class ActivityCell(BaseModel):
    """One cell in the activity heat map: (date, count)."""
    date: str  # YYYY-MM-DD
    count: int


class ActivityHeatmapOut(BaseModel):
    """Activity heat map for a project (last 12 weeks by default)."""
    weeks: int
    cells: List[ActivityCell]
    total: int
    per_user: dict  # user_id -> List[ActivityCell]


class DigestEmailOut(BaseModel):
    id: str
    project_id: str
    subject: str
    body: str
    recipient: str
    sent_at: datetime
    delivery: str  # "logged" or "sent"

    class Config:
        from_attributes = True


class NotificationOut(BaseModel):
    id: str
    user_id: str
    project_id: Optional[str] = None
    type: str
    title: str
    body: Optional[str] = None
    link: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    # List of user_ids mentioned via @mention
    mentions: Optional[List[str]] = None


class CommentOut(BaseModel):
    id: str
    task_id: str
    user_id: str
    user_name: Optional[str] = None
    body: str
    mentions: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True


class AuditEntryOut(BaseModel):
    id: str
    task_id: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    action: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BulkTaskUpdate(BaseModel):
    task_ids: List[str] = Field(min_length=1, max_length=200)
    status: Optional[str] = None
    assignee_id: Optional[str] = None
    delete: Optional[bool] = None

