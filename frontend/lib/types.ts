export type UserRole = "student" | "instructor" | "admin";

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  avatar_url?: string | null;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export type TaskStatus = "todo" | "in_progress" | "review" | "done";

export interface Member {
  user_id: string;
  name: string;
  email: string;
  role: "leader" | "member";
  contribution_percent?: number | null;
}

export interface Project {
  id: string;
  title: string;
  description?: string | null;
  deadline: string;
  status: string;
  instructor_id?: string | null;
  created_at: string;
  members: Member[];
}

export interface ProjectSummary {
  project: Project;
  total_tasks: number;
  completed_tasks: number;
  overdue_tasks: number;
  cpm_project_duration?: number | null;
  cpm_estimated_completion?: string | null;
  cpm_delay_risk?: number | null;
  cpm_critical_path: string[];
}

export interface Task {
  id: string;
  project_id: string;
  assignee_id?: string | null;
  assignee_name?: string | null;
  title: string;
  description?: string | null;
  status: TaskStatus;
  story_points: number;
  priority: number;
  deadline?: string | null;
  completed_at?: string | null;
  depends_on: string[];
  early_start?: number | null;
  early_finish?: number | null;
  late_start?: number | null;
  late_finish?: number | null;
  slack?: number | null;
  is_critical: boolean;
  is_overdue: boolean;
  recurrence?: string | null;
  parent_task_id?: string | null;
  created_at: string;
}

export type Recurrence = "none" | "daily" | "weekly" | "biweekly" | "monthly";

export const RECURRENCE_OPTIONS: { id: Recurrence; label: string }[] = [
  { id: "none", label: "Không lặp" },
  { id: "daily", label: "Hàng ngày" },
  { id: "weekly", label: "Hàng tuần" },
  { id: "biweekly", label: "2 tuần / lần" },
  { id: "monthly", label: "Hàng tháng" },
];

export interface Meeting {
  id: string;
  project_id: string;
  title?: string | null;
  file_url?: string | null;
  file_type?: string | null;
  status: string;
  transcript?: string | null;
  created_at: string;
}

export type FilePreviewKind = "image" | "pdf" | "audio" | "video" | "text" | "binary";

export interface FileMeta {
  meetingId: string;
  filename: string;
  size: number;
  mime: string;
  kind: FilePreviewKind;
  previewUrl: string;
  downloadUrl: string;
  backend?: "local" | "s3";
}

export interface PresignedUpload {
  uploadUrl: string;
  key: string;
  method: "PUT";
  headers: Record<string, string>;
  expiresIn: number;
}

export interface SearchHit {
  id: string;
  title?: string | null;
  status?: string;
  project_id?: string;
  [k: string]: unknown;
}

export interface SearchResult {
  hits: SearchHit[];
  estimatedTotalHits?: number;
  backend?: "meilisearch" | "postgres-fallback" | string;
}

export interface WebhookSubscription {
  id: string;
  target: "generic" | "slack" | "discord";
  url: string;
  events: string[] | null;
  is_active: boolean;
  created_at: string;
}

export interface WebhookWithSecret extends WebhookSubscription {
  secret: string;
}

export interface WebhookDelivery {
  id: string;
  event: string;
  status: "pending" | "delivered" | "failed" | "dead";
  attempts: number;
  last_status_code: number | null;
  last_response: string | null;
  next_retry_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExtractedTask {
  id: string;
  meeting_id: string;
  task_data: Record<string, unknown>;
  is_approved: boolean;
  imported_task_id?: string | null;
  created_at: string;
}

export interface AIReport {
  id: string;
  project_id: string;
  report_text: string;
  contribution_snapshot?: Record<string, unknown> | null;
  created_at: string;
}

export interface DigestEmail {
  id: string;
  project_id: string;
  subject: string;
  body: string;
  recipient: string;
  delivery: "logged" | "sent" | "preview";
  sent_at: string;
}

export interface Notification {
  id: string;
  user_id: string;
  project_id?: string | null;
  type: string;
  title: string;
  body?: string | null;
  link?: string | null;
  is_read: boolean;
  created_at: string;
}

export interface TaskComment {
  id: string;
  task_id: string;
  user_id: string;
  user_name?: string | null;
  body: string;
  mentions: string[];
  created_at: string;
}

export interface AuditEntry {
  id: string;
  task_id: string;
  user_id?: string | null;
  user_name?: string | null;
  action: string;
  old_value?: string | null;
  new_value?: string | null;
  created_at: string;
}

export const KANBAN_COLUMNS: { id: TaskStatus; title: string; tone: string }[] = [
  { id: "todo", title: "To do", tone: "bg-gray-100" },
  { id: "in_progress", title: "In progress", tone: "bg-blue-100" },
  { id: "review", title: "Review", tone: "bg-yellow-100" },
  { id: "done", title: "Done", tone: "bg-green-100" },
];
