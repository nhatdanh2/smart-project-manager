"""Seed script: 3 users, 1 instructor, 2 projects, ~10 tasks with dependencies.

Usage (from the backend/ directory):
    python -m scripts.seed
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


# Make ``app`` importable when run as a script
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models.contribution import ContributionScore  # noqa: E402
from app.models.meeting import Meeting  # noqa: E402
from app.models.project import Project, ProjectMember  # noqa: E402
from app.models.task import Task, TaskHistory  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth_service import hash_password  # noqa: E402
from app.services.cpm_service import CPMTaskInput, calculate_cpm  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed")


def upsert_user(db, email: str, name: str, role: str, password: str = "password123") -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        name=name,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def add_history(db, task: Task, user: User, action: str, old: str | None, new: str | None) -> None:
    db.add(
        TaskHistory(
            id=str(uuid.uuid4()),
            task_id=task.id,
            user_id=user.id,
            action=action,
            old_value=old,
            new_value=new,
        )
    )


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            logger.info("Database already seeded - skipping")
            return

        instructor = upsert_user(
            db, "instructor@example.com", "TS. Nguyễn Văn A", "instructor"
        )
        leader = upsert_user(db, "leader@example.com", "Trần Thị B (Leader)", "student")
        member1 = upsert_user(db, "alice@example.com", "Lê Văn C", "student")
        member2 = upsert_user(db, "bob@example.com", "Phạm Thị D", "student")
        member3 = upsert_user(db, "carol@example.com", "Hoàng Văn E", "student")
        db.commit()

        now = datetime.now(tz=timezone.utc)

        project_a = Project(
            id=str(uuid.uuid4()),
            title="Xây dựng website bán hàng thời trang",
            description="Đồ án cuối kỳ môn Lập trình Web - Nhóm 5",
            deadline=now + timedelta(days=30),
            status="active",
            instructor_id=instructor.id,
        )
        db.add(project_a)
        db.flush()
        for u, role in [
            (leader, "leader"),
            (member1, "member"),
            (member2, "member"),
            (member3, "member"),
        ]:
            db.add(
                ProjectMember(
                    project_id=project_a.id, user_id=u.id, role=role
                )
            )

        # Tasks with dependencies
        task_specs = [
            ("Khảo sát yêu cầu & đối thủ", "todo", leader.id, 2, [], -3),
            ("Thiết kế database & API", "done", member1.id, 3, [0], -1),
            ("Thiết kế UI/UX trên Figma", "done", member2.id, 3, [0], -2),
            ("Frontend: trang chủ + danh mục", "in_progress", member2.id, 5, [1, 2], 1),
            ("Frontend: giỏ hàng + thanh toán", "todo", member3.id, 5, [3], 5),
            ("Backend: API sản phẩm", "done", member1.id, 3, [1], 0),
            ("Backend: API đơn hàng", "in_progress", member1.id, 5, [5], 2),
            ("Tích hợp thanh toán VNPay", "todo", member3.id, 5, [4, 6], 8),
            ("Testing + sửa lỗi", "todo", leader.id, 3, [7], 12),
            ("Deploy lên Vercel + Railway", "todo", leader.id, 2, [8], 15),
        ]
        tasks: list[Task] = []
        for i, (title, status, assignee, sp, deps, day_offset) in enumerate(task_specs):
            t = Task(
                id=str(uuid.uuid4()),
                project_id=project_a.id,
                assignee_id=assignee,
                title=title,
                status=status,
                story_points=sp,
            )
            t.depends_on = [tasks[j].id for j in deps]
            if status == "done":
                t.completed_at = now - timedelta(days=1)
            t.deadline = now + timedelta(days=day_offset)
            db.add(t)
            db.flush()
            add_history(db, t, leader, "created", None, "todo")
            if status != "todo":
                add_history(db, t, leader, "status_changed", "todo", status)
            tasks.append(t)

        # Recompute CPM
        cpm = calculate_cpm(
            tasks=[
                CPMTaskInput(
                    id=t.id, title=t.title, story_points=t.story_points, depends_on=t.depends_on
                )
                for t in tasks
            ],
            deadline=project_a.deadline,
        )
        by_id = {r.id: r for r in cpm.tasks}
        for t in tasks:
            r = by_id[t.id]
            t.early_start = r.early_start
            t.early_finish = r.early_finish
            t.late_start = r.late_start
            t.late_finish = r.late_finish
            t.slack = r.slack
            t.is_critical = r.is_critical

        # Sample meeting
        meeting = Meeting(
            id=str(uuid.uuid4()),
            project_id=project_a.id,
            title="Biên bản họp tuần 1",
            file_type="text",
            transcript=(
                "Cuộc họp nhóm ngày 1/6. Trần Thị B sẽ phụ trách khảo sát yêu cầu. "
                "Lê Văn C cần hoàn thành thiết kế database trước thứ 6. "
                "Phạm Thị D sẽ làm UI trên Figma. Hoàng Văn E phụ trách frontend giỏ hàng."
            ),
            status="done",
            created_by=leader.id,
        )
        db.add(meeting)
        db.commit()
        db.refresh(project_a)
        logger.info("Seeded project %s with %d tasks", project_a.id, len(tasks))
        logger.info("Login credentials (password = 'password123'):")
        logger.info("  instructor@example.com  (instructor)")
        logger.info("  leader@example.com     (student, leader of project)")
        logger.info("  alice@example.com      (student)")
        logger.info("  bob@example.com        (student)")
        logger.info("  carol@example.com      (student)")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
