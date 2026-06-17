# Smart Student Project Manager — Frontend

Next.js 14 (App Router) + TypeScript + Tailwind + Recharts.

## Quick start

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev   # http://localhost:3000
```

The frontend talks to the FastAPI backend on `http://localhost:8000`
by default (override with `NEXT_PUBLIC_API_URL`).

## Pages

- `/` — landing
- `/login`, `/register` — auth
- `/projects` — danh sách dự án (card có nút xóa)
- `/projects/[id]/overview` — tổng quan + AI report + PDF export + dependency graph
- `/projects/[id]/kanban` — Kanban với drag & drop + edit modal
- `/projects/[id]/gantt` — Gantt chart với critical path
- `/projects/[id]/calendar` — **Calendar view** deadline theo tháng
- `/projects/[id]/members` — điểm đóng góp + radar + heat map + invite modal
- `/projects/[id]/meeting` — upload biên bản + AI trích xuất task (Whisper cho audio)
- `/projects/[id]/digest` — email digest preview + send + history + webhooks
- `/instructor` — dashboard giảng viên

## Components

- `KanbanBoard` — dnd-kit board với optimistic updates, **multi-select với floating bulk toolbar**
- `GanttChart` — SVG thuần, dependency arrows, click để xem chi tiết
- `DependencyGraph` — topological layout cho overview tab
- `TaskDetailPanel` — **3 tab UI** (Details/Comments/Audit) với @mention trong comment
- `ActivityHeatMap` — 12-tuần heat map + per-member mini heatmap
- `CalendarView` — month grid với task deadline markers
- `NotificationBell` — bell với dropdown + realtime WebSocket + toast
- `ThemeProvider` + `ThemeToggle` — dark mode với persist
- `I18nProvider` + `LanguageSwitcher` — VI/EN dictionary
- `ErrorBoundary` — error UI thân thiện
- `Skeletons` — loading states

## UI Primitives (`components/ui/`)

Build trên Radix UI + CVA + class-variance-authority, dễ dùng lại:

- `Button` — 6 variants (primary, secondary, danger, ghost, outline, link) × 4 sizes
- `Input` / `Textarea` / `Select` — với dark mode
- `Card` (Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter)
- `Badge` — 6 variants
- `Checkbox` — Radix-based, accessible
- `Dialog` (Dialog, DialogTrigger, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription) — Radix-based với animation

Khi cần component mới, tạo theo pattern tương tự.

## Theme

Dark mode là **class-based** (`darkMode: "class"` trong `tailwind.config.js`).
ThemeProvider lưu lựa chọn vào `localStorage` (`spm_theme`) và respect
`prefers-color-scheme` nếu người dùng chưa chọn.

## i18n

Custom provider (`components/I18nProvider.tsx`) với dictionary trong
`lib/i18n.ts`.  Hiện hỗ trợ VI (mặc định) + EN.  Dùng `useI18n()` hook
trong component: `const { t } = useI18n(); t("nav.projects")`.  Chọn ngôn
ngữ từ sidebar (`LanguageSwitcher`).

## WebSocket

Hai kênh realtime:
- `ws://.../ws/projects/{id}?token=...` — per-project (kanban events, broadcasts)
- `ws://.../ws/me?token=...` — per-user (notifications)

Hook `useProjectWebSocket` cho project events, `useUserWebSocket` cho
notifications.  Cả hai tự reconnect với delay 2s.

## PDF Export

`lib/pdfExport.ts` dùng `jspdf` để render báo cáo AI thành PDF.
Lưu ý: font helvetica mặc định của jsPDF không hỗ trợ đầy đủ
tiếng Việt có dấu — mình strip diacritics để giữ readability.
Nếu cần dấu đầy đủ, cần embed font Unicode (.ttf) custom.

## Task Detail Panel

`components/TaskDetailPanel.tsx` — dialog với 3 tab:

1. **Details** — sửa title/description/status/story_points/priority/assignee/deadline, xóa task
2. **Comments** — chat-style với @mention (gõ `@` → popup gợi ý thành viên, click để chèn). Mention tạo notification
3. **Audit** — log mọi thay đổi (status_changed, bulk_*, created, …) với old → new value

## Bulk Operations

Trên Kanban, click checkbox góc trái mỗi card để multi-select. Khi
có selection, floating toolbar hiện ở dưới màn hình với 3 action:
- Chuyển status (hàng loạt)
- Gán assignee (hàng loạt)
- Xóa (hàng loạt)

Mỗi hành động tạo `TaskHistory` với action `bulk_*`.

## Roadmap (Phase 6+)

- File preview (PDF, image) trong meeting page
- Recurring tasks
- Real-time presence
- Mobile app (React Native)
- Sentry / OpenTelemetry tracing
- API rate limiting
