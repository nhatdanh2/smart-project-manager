# Smart Student Project Manager — "Ai đang gánh team?"

> Hệ thống quản lý đồ án nhóm với AI — phát hiện ghost member, dự báo trễ hạn bằng Critical Path Method, trích xuất task từ biên bản họp tự động.

## Tech stack

- **Frontend:** Next.js 14 (App Router) · TypeScript · Tailwind CSS · Recharts · @dnd-kit · sonner · jsPDF · Radix UI · class-variance-authority
- **Backend:** FastAPI · SQLAlchemy · Alembic · Celery + Redis (opt-in)
- **Database:** PostgreSQL 15 (production) · SQLite (local dev default)
- **AI:** Anthropic API (`claude-sonnet-4-6`) + OpenAI Whisper (audio) với stub fallback
- **Email:** Stub logger + Slack/Discord webhook broadcasts (production cần plug SMTP qua `SMTP_HOST`)
- **WebSocket:** In-process pub/sub (per-project + per-user channels)
- **i18n:** Custom provider + dictionaries (no heavy lib)
- **E2E:** Playwright
- **Realtime:** WebSocket (FastAPI native, in-process pub/sub)
- **Auth:** JWT (HS256) với refresh token rotation
- **Storage:** Local FS (`/uploads`) cho dev; S3-compatible client có thể bật qua env
- **Deployment:** Docker Compose

## Cấu trúc thư mục

```
smart-project-manager/
├── backend/             # FastAPI + SQLAlchemy
├── frontend/            # Next.js 14
├── docker-compose.yml   # Postgres + Redis + Backend + Frontend
├── .env.example
└── README.md
```

## Quick start (local, không cần Docker)

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                # Windows
# source .venv/bin/activate          # macOS / Linux
pip install -r requirements.txt
copy .env.example .env               # cp trên macOS/Linux
python -m scripts.seed               # tạo dữ liệu demo
uvicorn app.main:app --reload
```

API chạy ở <http://localhost:8000> · OpenAPI docs: `/docs`

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

App chạy ở <http://localhost:3000>

### Tài khoản demo (password = `password123`)

| Email                  | Vai trò              |
|------------------------|----------------------|
| `instructor@example.com` | Giảng viên         |
| `leader@example.com`     | Sinh viên (Leader) |
| `alice@example.com`      | Sinh viên          |
| `bob@example.com`        | Sinh viên          |
| `carol@example.com`      | Sinh viên          |

## Quick start (Docker)

```bash
cp .env.example .env                 # thêm ANTHROPIC_API_KEY nếu có
docker compose up --build
```

Để chạy kèm Celery worker:

```bash
docker compose --profile celery up --build
```

## Phase 1 — đã có

- ✅ Auth (register / login / refresh / me) bằng JWT
- ✅ Projects CRUD + quản lý thành viên
- ✅ Tasks CRUD + Kanban board (chuyển cột bằng dropdown, chưa drag & drop)
- ✅ Thuật toán CPM (cpm_service.py) + recompute khi task đổi
- ✅ Contribution scoring với công thức 0.4·0.35·0.15·0.1
- ✅ LLM Agent 1 (Secretary) — Claude API + stub fallback
- ✅ LLM Agent 2 (Advisor) — Claude API + stub fallback
- ✅ Upload biên bản (.txt/.md/.pdf/.mp3/.wav) + AI trích xuất task
- ✅ Dashboard giảng viên + ghost member detection
- ✅ WebSocket realtime cho Kanban events
- ✅ In-process Celery stub (bật bằng `USE_CELERY=true`)
- ✅ Alembic config (init migration sẵn sàng cho Postgres)
- ✅ Unit tests cho CPM & Contribution
- ✅ User search endpoint (`/api/users/search`)

## Phase 2 — đã có

- ✅ **Drag & drop Kanban** với `@dnd-kit` (kéo qua lại giữa các cột + sắp xếp lại trong cùng cột)
- ✅ **Gantt chart** (SVG thuần) với critical path đỏ, dependency arrows, click để xem chi tiết
- ✅ **Whisper transcription** cho audio meetings (OpenAI API + stub fallback tiếng Việt)
- ✅ **Toast notifications** toàn cục (sonner) — tạo/xóa/AI actions đều có feedback
- ✅ **Dependency graph** trên tab Tổng quan (topological layout SVG)
- ✅ **Task edit modal** với priority, status, deadline, dependencies
- ✅ **User search & invite** modal trên tab Thành viên
- ✅ **Error boundary** + **skeleton loading** + responsive polish
- ✅ Task `priority` (reorder trong cùng cột) — backend persist

## Phase 3 — đã có

- ✅ **Dark mode** (toggle trong sidebar, persist trong localStorage, system preference detect, mọi card/modal/table tương thích)
- ✅ **PDF export** AI reports (jsPDF, có header, footer, multi-page)
- ✅ **Heat map** hoạt động 12 tuần (GitHub-style) + per-member mini heatmap
- ✅ **Mobile responsive** (collapsible sidebar với drawer animation, mobile top bar, theme toggle mobile, padding responsive)
- ✅ **Email digest service** (compose + log + persist, endpoint preview/send/history)
- ✅ **Email digest UI** (tab mới trong project detail: preview + send + history)

## Phase 4 — đã có

- ✅ **Notification bell** với WebSocket per-user (`/ws/me`) + dropdown + toast realtime
- ✅ **Notification model** + service + REST endpoints (list, unread count, mark read, mark all read)
- ✅ **Auto-notify** khi: task assigned, task done, meeting uploaded, member added
- ✅ **Calendar view** (tháng) với deadline markers + overdue highlighting
- ✅ **i18n** (VI/EN) với provider + dictionary + language switcher trong sidebar
- ✅ **Slack/Discord/Teams webhooks** cho digest (Slack-compatible payload, leader-only CRUD)
- ✅ **E2E tests** với Playwright (3 specs: landing, auth+project, theme)

## Phase 5 — đã có

- ✅ **UI primitives** (shadcn-style): `Button` (CVA variants), `Input`/`Textarea`/`Select`, `Card`, `Badge`, `Checkbox`, `Dialog` (Radix)
- ✅ **Task comments** với model + API + 3 tab UI (Details / Comments / Audit) trong TaskDetailPanel
- ✅ **@mention** trong comment — popup gợi ý người khi gõ `@`, tự detect mention từ text, gửi notification cho người được nhắc
- ✅ **Bulk operations** — multi-select task trên Kanban (checkbox), floating toolbar với batch status/assignee/delete
- ✅ **Audit log UI** — tab "Lịch sử" trong TaskDetailPanel hiển thị TaskHistory với action label + old → new value
- ✅ **Refactor** Login, Register, Projects list dùng UI primitives mới

## Phase 6 — đã có

- ✅ **Recurring tasks** — task có `recurrence` (`daily`/`weekly`/`biweekly`/`monthly`). Khi chuyển task sang `done`, backend tự spawn task mới với deadline +1 ngày/tuần/2-tuần/tháng. UI có select ở form tạo + edit task; card trên Kanban có badge `🔁`. Service: `app/services/recurrence_service.py`.
- ✅ **Real-time presence** — WS endpoint `/ws/projects/{id}` đồng thời track ai đang connect, broadcast `presence` event mỗi khi thành viên join/leave/heartbeat (TTL 90s). Frontend có `useProjectPresence` hook + `PresenceAvatars` component (stack avatar + popover) hiển thị ở header Kanban. Service: `app/services/presence_service.py`. REST: `GET /api/ws/projects/{id}/presence`.
- ✅ **API rate limiting** — `slowapi` + `limits`. Key là `user:<sub>` cho request có Bearer token, ngược lại `ip:<addr>`. Default 120 req/min/user, riêng AI 10/min, upload 20/min, login/register 10/min. Cấu hình qua env (`RATE_LIMIT_*`). 429 trả JSON; frontend interceptor hiển thị toast "Quá nhiều yêu cầu…". Module: `app/rate_limit.py`.

## Phase 7 — đã có

- ✅ **File preview (PDF, image, audio, video, text)** — backend `GET /api/files/meetings/{id}/preview` stream file với đúng `Content-Type` + hỗ trợ HTTP `Range` (scrub video/audio). `GET /api/files/meetings/{id}/meta` trả `{mime, kind, size}` để frontend chọn viewer. Path-traversal guard chống truy cập ngoài `UPLOAD_DIR`. Frontend `FilePreviewModal` dùng Radix `Dialog` + UI primitives: `<img>`, `<iframe>` (PDF), `<audio>`, `<video>`, `<pre>` cho text/JSON. Mở từ nút `👁 Xem` trong meeting page. Module: `app/services/file_service.py`, router: `app/routers/files.py`.
- ✅ **Sentry (error tracking)** — backend `sentry-sdk[fastapi]` tích hợp FastAPI + SQLAlchemy + Logging, gọi `capture_exception` trong global exception handler. Frontend `@sentry/nextjs` với `browserTracingIntegration` + replay, gọi qua `lib/observability.ts` (lazy import). `global-error.tsx` bắt lỗi root layout. Cả 2 bên đều no-op khi `SENTRY_DSN`/`NEXT_PUBLIC_SENTRY_DSN` rỗng.
- ✅ **OpenTelemetry (distributed tracing)** — backend tự động instrument FastAPI + SQLAlchemy + httpx, export OTLP/gRPC tới collector (Jaeger/Tempo/Honeycomb…). `instrument_app()` được gọi trong startup. Sample rate + endpoint qua env.
- ✅ **Kubernetes manifests** — folder `k8s/` đầy đủ: Namespace, ConfigMap + Secret, Postgres StatefulSet + PVC, Redis, Backend (Deployment + init migrate + healthcheck), Celery worker, Frontend, Ingress (NGINX + WebSocket + cert-manager), HPA autoscaler (CPU/mem), NetworkPolicies. Production-ready Dockerfile frontend multi-stage. Sentry/OTel/Postgres secrets được tách riêng.

## Phase 8 — đã có

- ✅ **CI pipeline (GitHub Actions)** — `.github/workflows/ci.yml` chạy 3 jobs song song trên PR + push: `backend` (ruff + mypy + pytest với Postgres/Redis service containers, fallback `continue-on-error` cho typecheck/tests khi chưa đủ coverage), `frontend` (lint + tsc + `next build`), `e2e` (Playwright, upload report on failure). Thêm `backend/pyproject.toml` cấu hình ruff/mypy, `backend/tests/conftest.py` + `test_smoke.py` (3 tests cơ bản).
- ✅ **CD pipeline (GitHub Actions)** — `.github/workflows/cd.yml` build & push 2 images lên **GHCR** với Buildx cache (GHA), metadata tags (branch/sha/semver/latest), provenance, build-args cho Next.js public URLs. Tự động chạy khi push main hoặc tag `v*.*.*`.
- ✅ **Deploy workflow** — `.github/workflows/deploy.yml` chạy `helm upgrade --install` với image tag từ release / sha, smoke test `/health`. Hỗ trợ staging/production environments với GitHub Environment secrets (JWT, DB password, AI keys, Sentry DSN).
- ✅ **Helm chart** — `helm/smart-pm/` gồm `Chart.yaml`, `values.yaml` (mọi thứ configurable: replicaCount, image tag, autoscaling, ingress, secrets, env, persistence), `values.prod.yaml` mẫu, README hướng dẫn. Templates: namespace, service account, secret, configmap, postgres StatefulSet (opt-out), redis Deployment (opt-out), backend Deployment (init migrate + healthchecks), celery worker, frontend Deployment, ingress (multi-host với TLS), HPA (3 targets), network policies. Init-container `wait-for-db` + `alembic upgrade head` chạy trước khi API lên.
- ✅ **Production docker-compose** — `docker-compose.prod.yml` với healthchecks strict, `restart: unless-stopped`, no bind mounts, no `--reload`, non-root user, resource limits, image tags pinned. Optional Caddy reverse proxy profile (`--profile with-proxy`) + `deploy/Caddyfile` tự động Let's Encrypt + security headers. `.env.prod.example` template.

## Phase 9 — đã có

- ✅ **Alembic migrations** — folder `backend/alembic/` với `alembic.ini`, `env.py` (đọc `DATABASE_URL` từ `app.config.settings`, hỗ trợ autogenerate + render_as_batch cho SQLite), `script.py.mako`. Migration `0001_initial.py` tạo toàn bộ schema (12 bảng, đầy đủ FK + index). `init_db()` giờ auto-detect `alembic_version` table — no-op khi đang dùng migrations, tránh drift. Helm `backend` init-container tự chạy `alembic upgrade head`. README hướng dẫn `alembic revision --autogenerate -m "…"`.
- ✅ **E2E test suite (Playwright)** — folder `e2e/` với `playwright.config.ts` (2 projects: chromium + firefox, auto-start docker stack qua `webServer`, health check trong `global-setup.ts`, `PLAYWRIGHT_BASE_URL` để chạy trên staging). 4 specs:
  - `auth.spec.ts` — register → login → /me round trip, 401 sai password, 401 thiếu token, 429 sau 10 lần login fail/min
  - `kanban.spec.ts` — create project → recurring weekly task → move to done → spawn next occurrence; CPM recalc với dependency chain
  - `file-preview.spec.ts` — upload PNG inline, meta + preview stream bytes đúng length, `Range: bytes=0-9` trả 206 + 10 bytes, 403 nếu không phải member
  - `presence.spec.ts` — 2 users WS-connect, presence event chứa cả 2 userId
- ✅ **Terraform (AWS infrastructure)** — folder `terraform/` với `main.tf` (VPC 2 AZ + NAT, EKS 1.29 với system + spot node groups, RDS Postgres 16 gp3 + Multi-AZ cho prod + Performance Insights, ElastiCache Redis 7 encrypted + AUTH, S3 uploads với versioning + encryption + public block, ACM cert cho ALB), `variables.tf` (validation cho environment), `terraform.tfvars.example`, `.gitignore`, README với cost estimate (~$430/mo prod). Có thể kết nối thẳng với `deploy` GitHub Actions workflow (GitHub Environment secrets = TF_VAR values).

## Phase 10 — đã có

- ✅ **GDPR — data export** — `GET /api/gdpr/export` trả JSON archive toàn bộ data của user (user, projects_member_of, tasks, meetings, notifications, contributions, digest_emails). Content-Disposition: attachment. Migrations `0002_gdpr_soft_delete` thêm `is_active`, `anonymized_at`, `deletion_requested_at`; `0003_gdpr_audit` tạo bảng `gdpr_audit_logs` (action, actor, ip, user_agent, extra JSON). Mọi action (export, delete.requested, delete.cancelled, delete.purged, admin.recover) đều ghi audit log.
- ✅ **GDPR — account deletion với grace period** — `POST /api/gdpr/delete` soft-delete (anonymise email thành `deleted-<uuid>@deleted.invalid`, set `is_active=false`, hash password random). User không login được. Sau 30 ngày (configurable `GDPR_DELETION_GRACE_DAYS`) Celery beat task `gdpr.purge_task` chạy `purge_expired_deletions()` → null FK trong task_history/notifications/comments/contributions (giữ row cho project context), xóa project_members, xóa user. Trước khi hết grace có thể `POST /api/gdpr/cancel` để recover. Admin có thể `POST /api/gdpr/admin/recover/{user_id}` và `POST /api/gdpr/admin/purge-expired`. Module: `app/services/gdpr_service.py`, `app/services/audit_service.py`, `app/jobs/gdpr_purge_job.py`. E2E tests trong `e2e/tests/gdpr.spec.ts`.
- ✅ **S3 presigned URLs** — `app/services/s3_service.py` với boto3, tự detect `S3_BUCKET_NAME` (no-op nếu rỗng, fallback local FS). `POST /api/files/presign-upload?project_id=…&filename=…&content_type=…` trả `{uploadUrl, key, method, headers, expiresIn}` (15 phút). File router `/meta` endpoint giờ trả `backend: "s3" | "local"` + presigned GET URL khi dùng S3 (browser download thẳng từ S3, không qua API). Upload meeting endpoint chấp nhận `s3_key` form field thay cho multipart file.
- ✅ **S3 direct upload frontend** — `lib/s3-upload.ts` dùng `XMLHttpRequest` để PUT file thẳng lên S3 với progress callback (FE có progress bar realtime). Meeting page try-catch giữa S3 direct và multipart fallback, không phá flow cũ. Thêm `boto3==1.35.36` vào requirements.
- ✅ **Meilisearch search engine** — `app/services/search_service.py` lazy-import SDK, `is_enabled()` check URL. Indexes: `tasks` (searchable: title/description/project_title, filterable: project_id/status/assignee_id, sortable: created_at/deadline) + `meetings` (title/transcript). `ensure_indexes()` chạy trong startup hook. `create_task` tự index với `index_task({...})`. Search endpoint `GET /api/projects/{id}/search?q=…&index=tasks|meetings&status=…&assignee_id=…&limit=…&offset=…` trả `{hits, estimatedTotalHits, backend}`. Postgres ILIKE fallback nếu Meilisearch chưa bật.
- ✅ **Frontend search bar** — `components/SearchBar.tsx` với debounce 250ms, dropdown results có highlight matching text (`<mark>`), filter theo kind (tasks/meetings) + status, close-on-outside-click, click result navigate tới task hoặc meeting. Wire vào Kanban header. Meilisearch service thêm vào `docker-compose.yml` profile `search`.

## Phase 11 — đã có

- ✅ **Background services split-out** — toàn bộ job chuyển sang Celery beat:
  - `app/jobs/recurring_task_job.py` — `spawn_due_recurring_tasks()` gửi reminder khi recurring task quá hạn (idempotent, dedupe theo ngày)
  - `app/jobs/presence_cleanup_job.py` — `kick_stale_presence()` xoá user không heartbeat >45s
  - `app/jobs/search_reindex_job.py` — `reindex_all()` rebuild toàn bộ Meilisearch từ Postgres
  - `app/jobs/ai_extraction_job.py` — `extract_meeting_actions()` thay thế inline upload
  - `app/jobs/daily_digest_job.py` — `send_daily_digests()` tổng hợp mỗi user mỗi project
  - `app/jobs/webhook_dispatch_job.py` — `deliver_pending()` retry với backoff 0/1m/5m/30m
  - `app/jobs/gdpr_purge_job.py` — đã có từ Phase 10
- Tất cả registered trong Celery `beat_schedule`, có thể chạy trực tiếp qua `python -m app.jobs.<name>` trong dev.

## Phase 12 — đã có

- ✅ **Outbound webhooks** — `app/models/webhook.py` với `WebhookSubscription` (target: generic/slack/discord, URL, HMAC secret, event filter) + `WebhookDelivery` (status: pending/delivered/failed/dead, attempts, last_status_code, next_retry_at). 
- ✅ **Event dispatcher** — `app/services/webhook_service.py::emit_event()` chèn delivery row cho mọi subscription active match event. Wired vào `task.created`, `task.moved`, `task.completed`, `meeting.uploaded`, `member.joined`. Mỗi event có free-form `data.text` cho Slack/Discord.
- ✅ **Delivery job** — `app/jobs/webhook_dispatch_job.py` với HMAC SHA-256 `X-SmartPM-Signature`, async httpx, retry 0/1m/5m/30m, dead-letter sau 5 lần. 4xx (trừ 408/429) là permanent, không retry.
- ✅ **Frontend UI** — `components/WebhooksPanel.tsx` với form tạo (target + URL + event filter), rotate secret (hiển thị 1 lần), deliveries list (status, attempts, HTTP code, response body), thêm tab `/webhooks` vào project layout.

## Phase 13 — đã có

- ✅ **SAML 2.0 SSO** — `python3-saml` wrapper `app/services/saml_service.py`. Models: `SAMLSettings` (per-tenant IdP config, SP x509, attribute map, JIT config) + `SAMLAssertionLog` (audit every assertion). Endpoints:
  - `GET /api/saml/login?relay_state=/` → 302 to IdP AuthnRequest
  - `POST /api/saml/acs` → validate assertion, JIT-provision user, issue short-lived one-shot JWT, 302 back to SPA với `?saml_jwt=…`
  - `POST /api/saml/exchange` → trade one-shot JWT for normal access/refresh pair
  - `GET /api/saml/metadata` → SP metadata XML
  - `GET/PUT /api/saml/settings` (admin) → IdP config
  - `GET /api/saml/status` (public) → frontend probe để show/hide nút SSO
- ✅ **JIT provisioning** — auto-create user với email/name/role từ assertion, enforce `allowed_email_domains` (optional), update name/role on re-login, refuse if `is_active=false`. Migrations `0005_saml`.
- ✅ **Frontend SSO flow** — `app/sso-callback/page.tsx` exchange JWT rồi redirect dashboard. Login page thêm nút "🔐 Đăng nhập bằng SSO" (chỉ hiện khi `GET /api/saml/status.enabled=true`).

## Phase 14 — đã có

- ✅ **S3 lifecycle** — `terraform/main.tf` thêm `aws_s3_bucket_lifecycle_configuration` với 2 rules:
  - `tier-to-glacier-then-expire` — 90d → Glacier, 365d → Deep Archive, 7 năm expire
  - `expire-tmp` — objects under `tmp/` expire sau 1 ngày
- ✅ **Cross-region replication (CRR)** — secondary provider `aws.secondary` ở `ap-southeast-3` (Jakarta), replica bucket với versioning, IAM role với policy cho `s3:GetReplicationConfiguration` + `s3:ReplicateObject`/`Delete`/`Tags`. `aws_s3_bucket_replication_configuration` với `delete_marker_replication`. Cost thêm ~$10/mo cho inter-region transfer.

## Phase 15 — đã có

- ✅ **Expo mobile app (React Native)** — folder `mobile/` với expo-router, TypeScript, Nativewind, TanStack Query. `app.json` khai báo iOS/Android config, biometric permission, notification channel.
- ✅ **Auth** — `src/providers/AuthProvider.tsx` với SecureStore tokens, auto-refresh on 401, route group protection. `expo-local-authentication` cho biometric login (Face ID / fingerprint).
- ✅ **Screens** — `app/(auth)/login.tsx`, `app/(auth)/register.tsx`, `app/(tabs)/{projects,notifications,profile}.tsx`, `app/projects/[id]/{kanban,meeting}.tsx`.
- ✅ **Push notifications** — `src/components/PushTokenRegistrar.tsx` đăng ký Expo push token với backend qua `POST /api/push/tokens`. Backend `expo-server-sdk` wrapper `app/services/push_service.py::send_to_user()` dispatch push mỗi khi tạo in-app notification. Tab tapped → deep link `data.link`.
- ✅ **Shared backend** — cùng FastAPI JWT (web + mobile dùng chung), same S3 backend, same Meilisearch.

## Phase 11+ — cần implement tiếp

- ⏳ Mobile app (React Native / Expo)
- ⏳ Background services split-out (recurrence, presence cleanup, AI) sang Celery beat tasks thay vì in-process
- ⏳ Webhooks (outbound) — notify Slack/Discord khi task done
- ⏳ SAML SSO cho trường học / doanh nghiệp
- ⏳ S3 lifecycle policy (Glacier sau 90 ngày) + cross-region replication

## API endpoints (rút gọn)

```
POST   /api/auth/register
POST   /api/auth/login
POST   /api/auth/refresh
GET    /api/auth/me

GET    /api/projects
POST   /api/projects
GET    /api/projects/{id}
PUT    /api/projects/{id}
DELETE /api/projects/{id}
POST   /api/projects/{id}/members
DELETE /api/projects/{id}/members/{uid}
GET    /api/projects/{id}/summary
GET    /api/projects/{id}/contributions

GET    /api/projects/{id}/tasks
POST   /api/projects/{id}/tasks
PUT    /api/tasks/{id}
PUT    /api/tasks/{id}/move
DELETE /api/tasks/{id}
POST   /api/projects/{id}/cpm/recalculate

POST   /api/projects/{id}/meetings
GET    /api/projects/{id}/meetings
GET    /api/meetings/{id}
POST   /api/meetings/{id}/extract
GET    /api/meetings/{id}/extracted
POST   /api/extracted-tasks/{id}/approve
POST   /api/extracted-tasks/{id}/reject

GET    /api/users/search?q=

POST   /api/projects/{id}/reports/generate
GET    /api/projects/{id}/reports
GET    /api/reports/{id}

GET    /api/projects/{id}/activity
POST   /api/projects/{id}/digest/send
GET    /api/projects/{id}/digest/preview
GET    /api/projects/{id}/digest/history

GET    /api/projects/{id}/webhooks
PUT    /api/projects/{id}/webhooks
GET    /api/projects/{id}/webhooks/{wid}/deliveries
POST   /api/projects/{id}/webhooks/{wid}/rotate

GET    /api/saml/status
GET    /api/saml/login
POST   /api/saml/acs
GET    /api/saml/metadata
POST   /api/saml/exchange
GET    /api/saml/settings
PUT    /api/saml/settings

POST   /api/push/tokens
DELETE /api/push/tokens/{token}
POST   /api/push/admin/broadcast

GET    /api/gdpr/export
POST   /api/gdpr/delete
POST   /api/gdpr/cancel
POST   /api/gdpr/admin/recover/{user_id}
POST   /api/gdpr/admin/purge-expired

GET    /api/projects/{id}/search
POST   /api/files/presign-upload

GET    /api/notifications
GET    /api/notifications/unread-count
POST   /api/notifications/{id}/read
POST   /api/notifications/read-all

GET    /api/tasks/{id}/comments
POST   /api/tasks/{id}/comments
GET    /api/tasks/{id}/audit

POST   /api/projects/{id}/tasks/bulk
GET    /api/projects/{id}/assignable

WS     /ws/projects/{id}?token=...
WS     /ws/me?token=...
```

## Tests

```bash
cd backend
pip install pytest
pytest -q
```

## Ghi chú

- Database mặc định là SQLite để zero-config. Đổi `DATABASE_URL` sang
  Postgres khi deploy. Lúc đó chạy `alembic upgrade head` thay vì
  dùng `init_db()` (auto-create).
- AI agents có stub fallback: nếu `ANTHROPIC_API_KEY` rỗng, hệ thống
  dùng heuristic / template đơn giản. Điền key thật vào `.env` để có
  kết quả chất lượng production.
- File upload lưu ở `backend/uploads/`. Giới hạn 10MB cho text, 50MB
  cho audio (cấu hình trong `app/config.py`).
- Cấu hình CORS đã mở cho `localhost:3000` mặc định.

## Operations runbook

### Day-1 (fresh deploy)

```bash
# 1. Provision infra
cd terraform
terraform init && terraform apply

# 2. Install chart
helm upgrade --install smart-pm ./helm/smart-pm \
  --namespace smart-pm --create-namespace \
  -f ./helm/smart-pm/values.prod.yaml

# 3. Seed an admin
kubectl exec -it deploy/smart-pm-backend -n smart-pm -- \
  python -c "from app.database import SessionLocal; \
  from app.models.user import User; \
  import uuid; \
  db=SessionLocal(); \
  u=User(id=str(uuid.uuid4()), email='admin@example.com', name='Admin', \
         password_hash='!TODO', role='admin'); \
  db.add(u); db.commit()"
```

### Scheduled jobs (Celery beat)

| Beat entry | Schedule | Purpose |
| --- | --- | --- |
| `gdpr.purge_expired` | daily | Hard-delete accounts past grace period |
| `recurring_task.reminder` | hourly | Ping assignee for overdue recurring tasks |
| `presence.cleanup` | 30s | Kick stale members from presence map |
| `search.reindex` | daily | Rebuild Meilisearch from Postgres |
| `daily_digest.send` | daily | Send per-user per-project email digest |
| `webhook.deliver` | 30s | Retry pending webhook deliveries |

Run a Celery beat in production alongside the worker:

```bash
celery -A app.workers.celery_app.celery_app beat --loglevel=INFO
celery -A app.workers.celery_app.celery_app worker --loglevel=INFO --concurrency=4
```

### Disaster recovery

* **DB** — RDS automated backup (14 days retention in prod) + point-in-time recovery.  Cross-AZ replica.
* **S3 uploads** — CRR to `ap-southeast-3`, transition to Glacier after 90d.
* **Config** — all secrets live in `kubectl secrets` (and GitHub Environment secrets for deploy).  Rotate via `kubectl create secret ... --from-literal=...` + `helm upgrade`.
* **Meilisearch** — stateful, snapshot to the same S3 bucket on a daily cron (`meilisearch dump`).

### Health checks

| URL | What it returns |
| --- | --- |
| `GET /health` | `{"status": "ok"}` (200) — used by K8s liveness |
| `GET /api/saml/status` | `{"enabled": bool, "label": "…"}` — public |
| `GET /api/search?…` | hits + `backend` field (meilisearch / postgres-fallback) |

### Common operations

```bash
# Tail logs
kubectl logs -n smart-pm -l app=smart-pm-backend -f

# Open a shell in a backend pod
kubectl exec -it deploy/smart-pm-backend -n smart-pm -- bash

# Manually trigger a Celery task
kubectl exec -it deploy/smart-pm-backend -n smart-pm -- \
  celery -A app.workers.celery_app.celery_app call app.workers.tasks.search_reindex_task

# Force-run a one-off job
kubectl exec -it deploy/smart-pm-backend -n smart-pm -- \
  python -m app.jobs.daily_digest_job
```

### Mobile app release

```bash
cd mobile
eas login
eas build --profile production --platform all
eas submit --platform ios      # opens App Store Connect
eas submit --platform android  # opens Google Play Console
```
