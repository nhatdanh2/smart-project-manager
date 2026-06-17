# Smart Student Project Manager — Backend

FastAPI + SQLAlchemy + Celery + Anthropic Claude API.

## Quick start (local dev, no Docker)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS / Linux
pip install -r requirements.txt
copy .env.example .env         # macOS: cp .env.example .env
python -m scripts.seed         # creates demo data
uvicorn app.main:app --reload  # http://localhost:8000
```

OpenAPI docs: <http://localhost:8000/docs>

Demo accounts (password = `password123`):

| Email                  | Role       |
|------------------------|------------|
| instructor@example.com | instructor |
| leader@example.com     | student (leader) |
| alice@example.com      | student |
| bob@example.com        | student |
| carol@example.com      | student |

## Quick start (Docker)

```bash
docker compose up --build
```

The compose file provisions Postgres, Redis, the API server, a Celery
worker and the Next.js frontend.  In Docker mode, `DATABASE_URL` is set
automatically to point at the Postgres service.

## Project layout

```
backend/app/
├── main.py             # FastAPI entry
├── config.py           # env-based settings
├── database.py         # SQLAlchemy engine + Base
├── models/             # ORM models (User, Project, Task, Meeting, AIReport, DigestEmail, Notification, TaskComment, ...)
├── schemas/            # Pydantic schemas
├── routers/            # HTTP & WebSocket routes (auth, projects, tasks, members, meetings, ai, email_digest, notifications, users, ws)
├── services/           # CPM, contribution, AI agents, auth, realtime, email_digest, activity, transcription, notification, webhook
└── workers/            # Celery tasks
```

## Real-time

Two WebSocket channels:

- `/ws/projects/{id}?token=...` — per-project broadcast (used by Kanban)
- `/ws/me?token=...` — per-user (used by the notification bell)

In-process pub/sub via `app.services.realtime`.  Easy to swap for Redis
when scaling out.

## Auto-notifications

The notification service (`app.services.notification_service`) hooks
into key events:

| Event | Recipient |
|-------|-----------|
| `task.assigned` | The task's assignee (excludes creator) |
| `task.done`     | Project leader(s) (excludes mover) |
| `meeting.uploaded` | All project members (excludes uploader) |
| `member.added`  | The new member |
| `mention`       | The mentioned user(s) |
| `comment.added` | Task assignee (excludes commenter + already-mentioned) |

All notifications are persisted to the `notifications` table AND
pushed to `/ws/me` for real-time bell updates.

## Tests

```bash
pip install pytest
pytest
```

The CPM and contribution services ship with unit tests in `tests/`.
