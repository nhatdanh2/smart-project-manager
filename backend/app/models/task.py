"""Task and TaskHistory models.

Note: PostgreSQL UUID[] arrays (depends_on) are stored as a JSON string
in SQLite for portability. The application layer always serialises via
``json.dumps``/``json.loads``.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignee_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="todo", nullable=False)
    story_points: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # CPM fields
    depends_on_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    early_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    early_finish: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    late_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    late_finish: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    slack: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_critical: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Recurrence fields
    # One of: null, "daily", "weekly", "biweekly", "monthly"
    recurrence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # id of the original task (for generated occurrences)
    parent_task_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    history: Mapped[List["TaskHistory"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    @property
    def depends_on(self) -> List[str]:
        import json

        if not self.depends_on_json:
            return []
        try:
            return list(json.loads(self.depends_on_json))
        except Exception:
            return []

    @depends_on.setter
    def depends_on(self, value: Optional[List[str]]) -> None:
        import json

        self.depends_on_json = json.dumps(list(value or []))


class TaskHistory(Base):
    __tablename__ = "task_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped["Task"] = relationship(back_populates="history")
