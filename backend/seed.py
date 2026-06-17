"""Seed dữ liệu mẫu cho Smart PM.

Chạy::

    cd backend
    python -m seed
    # hoặc
    python seed.py

Xóa sạch DB rồi tạo:

* 4 user: Nguyễn Văn An (leader), Trần Thị Bình, Lê Văn Cường, Phạm Thị Dung
* 1 instructor Nguyễn Minh Giáo
* 1 project: "Xây dựng app thương mại điện tử" deadline 30 ngày
* 12 task có dependencies để CPM có critical path rõ ràng
* Một số task đã done để demo "gánh team" (An + Cường) và "ghost" (Bình)

Tất cả user có password là ``password123`` (đã hash bằng bcrypt).
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow ``python seed.py`` from the backend/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Project,
    ProjectMember,
    Task,
    TaskHistory,
    User,
)
from app.services.auth_service import hash_password  # noqa: E402


logger = logging.getLogger("seed")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def reset_schema() -> None:
    """Drop everything and recreate — destructive, dev only."""
    logger.info("Dropping & recreating all tables…")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def make_user(db, *, email: str, name: str, role: str = "student") -> User:
    u = User(
        email=email,
        name=name,
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(u)
    db.flush()
    return u


def add_member(db, *, project_id: str, user_id: str, role: str = "member") -> None:
    db.add(ProjectMember(project_id=project_id, user_id=user_id, role=role))


# -----------------------------------------------------------------------------
# Seed
# -----------------------------------------------------------------------------
def seed() -> dict:
    db = SessionLocal()
    try:
        reset_schema()

        # ----- Users ---------------------------------------------------------
        instructor = make_user(
            db,
            email="giao.lecturer@example.com",
            name="Nguyễn Minh Giáo",
            role="instructor",
        )
        an = make_user(
            db,
            email="an.leader@example.com",
            name="Nguyễn Văn An",
            role="student",
        )
        binh = make_user(
            db,
            email="binh.member@example.com",
            name="Trần Thị Bình",
            role="student",
        )
        cuong = make_user(
            db,
            email="cuong.member@example.com",
            name="Lê Văn Cường",
            role="student",
        )
        dung = make_user(
            db,
            email="dung.member@example.com",
            name="Phạm Thị Dung",
            role="student",
        )
        logger.info("Created 5 users (1 instructor + 4 students).")

        # ----- Project -------------------------------------------------------
        now = datetime.now(timezone.utc)
        project = Project(
            title="Xây dựng app thương mại điện tử",
            description=(
                "Đồ án nhóm cuối kỳ môn Lập trình Web. Sinh viên xây dựng một "
                "sàn thương mại điện tử mini (React + FastAPI) với các chức năng: "
                "đăng ký/đăng nhập, danh sách sản phẩm, giỏ hàng, thanh toán mock, "
                "và dashboard quản trị."
            ),
            deadline=now + timedelta(days=30),
            status="active",
            instructor_id=instructor.id,
        )
        db.add(project)
        db.flush()

        add_member(db, project_id=project.id, user_id=an.id, role="leader")
        add_member(db, project_id=project.id, user_id=binh.id, role="member")
        add_member(db, project_id=project.id, user_id=cuong.id, role="member")
        add_member(db, project_id=project.id, user_id=dung.id, role="member")
        logger.info("Created project '%s' with 4 student members.", project.title)

        # ----- Tasks ---------------------------------------------------------
        # Spec: 12 tasks with the exact dependencies from the PRD.
        # An + Cường = gánh team (nhiều task done)
        # Dung = trung bình
        # Bình = ghost (không hoàn thành gì cả)
        spec = [
            # (title, sp, assignee_id, depends_on_titles, status)
            # --- Setup phase (all done) ---
            ("Phân tích yêu cầu",                  3, an.id,    [],                            "done"),
            ("Thiết kế database",                  5, cuong.id, ["Phân tích yêu cầu"],         "done"),  # swap to Cường
            ("Thiết kế UI/UX",                     5, dung.id,  ["Phân tích yêu cầu"],         "done"),
            ("Setup môi trường dev",               2, cuong.id, [],                            "done"),
            # --- Implementation phase (mix done / in_progress) ---
            ("Backend API authentication",         5, an.id,    ["Thiết kế database", "Setup môi trường dev"], "done"),       # An done
            ("Backend API sản phẩm",               8, cuong.id, ["Thiết kế database", "Setup môi trường dev"], "done"),       # Cường done
            ("Frontend trang chủ",                 5, dung.id,  ["Thiết kế UI/UX", "Setup môi trường dev"], "done"),          # Dung done
            ("Frontend giỏ hàng",                 5, dung.id,  ["Thiết kế UI/UX", "Frontend trang chủ"], "in_progress"),     # Dung in_progress
            ("Tích hợp thanh toán",               8, an.id,    ["Backend API authentication", "Backend API sản phẩm"], "in_progress"),  # An in_progress
            ("Testing",                           3, cuong.id, ["Frontend giỏ hàng", "Tích hợp thanh toán"], "todo"),
            ("Fix bugs",                          3, cuong.id, ["Testing"],                   "todo"),
            ("Deploy",                            2, an.id,    ["Fix bugs"],                  "todo"),
        ]
        # Demo "ghost member": Bình nhận task nhưng chưa hoàn thành cái nào.
        # We add a single ghost task for Bình (todo) so he still appears
        # in the members list.
        binh_ghost = ("Tích hợp CI/CD", 2, binh.id, ["Setup môi trường dev"], "todo")
        spec.append(binh_ghost)

        title_to_id: dict[str, str] = {}
        # First pass: create tasks without deps so we have IDs
        for title, sp, assignee_id, _deps, status in spec:
            t = Task(
                project_id=project.id,
                title=title,
                description=f"Mô tả chi tiết cho task '{title}'. Sinh viên tự bổ sung.",
                status=status,
                story_points=sp,
                priority=0,  # we'll re-rank after
                assignee_id=assignee_id,
                deadline=now + timedelta(days=30),
            )
            db.add(t)
            db.flush()
            title_to_id[title] = t.id

        # Second pass: wire dependencies + priority + history
        for idx, (title, sp, assignee_id, deps, status) in enumerate(spec):
            t = db.query(Task).filter(Task.id == title_to_id[title]).first()
            t.priority = (idx + 1) * 10
            t.depends_on = [title_to_id[d] for d in deps if d in title_to_id]
            if status == "done":
                t.completed_at = now - timedelta(days=15 - idx)
            db.add(
                TaskHistory(
                    task_id=t.id,
                    user_id=assignee_id,
                    action="created",
                    new_value="todo",
                )
            )
            if status != "todo":
                db.add(
                    TaskHistory(
                        task_id=t.id,
                        user_id=assignee_id,
                        action="status_changed",
                        old_value="todo",
                        new_value=status,
                    )
                )

        db.commit()
        logger.info("Created 12 tasks with dependencies.")

        # ----- Recalculate CPM + contribution so FE renders nicely ---------
        try:
            from app.workers.tasks import recalculate_cpm, calculate_all_contributions
            recalculate_cpm(project.id)
            calculate_all_contributions(project.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Post-seed recalc skipped: %s", exc)
        # ----- One demo meeting so the meeting page isn't empty -----------
        from app.models.meeting import Meeting
        meeting = Meeting(
            project_id=project.id,
            title="Biên bản họp tuần 1",
            file_url=None,
            file_type="text",
            transcript=(
                "Cuộc họp ngày đầu tiên của nhóm. An phụ trách phân tích yêu cầu và "
                "sẽ hoàn thành trong 3 ngày tới. Bình cần thiết kế database sau khi "
                "An xong phân tích. Dung sẽ thiết kế UI/UX song song. Cường sẽ "
                "setup môi trường dev và Docker. Deadline nộp bản demo đầu tiên là "
                "2 tuần tới. Cả nhóm thống nhất sẽ họp lại vào thứ 6 tuần sau để "
                "review tiến độ."
            ),
            status="done",
            created_by=an.id,
        )
        db.add(meeting)
        db.commit()
        logger.info("Created demo meeting '%s'.", meeting.title)

        return {
            "users": 5,
            "project": project.id,
            "tasks": 13,
            "meeting": meeting.id,
        }
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Skip the destructive drop_all (append to existing data)",
    )
    args = parser.parse_args()

    if not args.keep:
        # In --keep mode we still want to be sure the tables exist.
        Base.metadata.create_all(bind=engine)

    result = seed()
    logger.info("Seed complete: %s", result)
    logger.info("Login with any of: an.leader@example.com / password123")
