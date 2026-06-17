"use client";

import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, RefreshCw, Trash2 } from "lucide-react";

import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { useProjectWebSocket } from "@/hooks/useWebSocket";
import { useProjectPresence } from "@/hooks/useProjectPresence";
import { KANBAN_COLUMNS, RECURRENCE_OPTIONS, type Project, type Recurrence, type Task, type TaskStatus } from "@/lib/types";
import { useI18n } from "@/components/I18nProvider";
import { KanbanBoard } from "@/components/KanbanBoard";
import { PresenceAvatars } from "@/components/PresenceAvatars";
import { SearchBar } from "@/components/SearchBar";
import { TaskDetailPanel } from "@/components/TaskDetailPanel";
import { KanbanSkeleton } from "@/components/Skeletons";

export default function KanbanPage() {
  const params = useParams<{ id: string }>();
  const { user } = useAuth(false);
  const { t } = useI18n();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    title: "",
    description: "",
    story_points: 1,
    assignee_id: "",
    deadline: "",
    status: "todo" as TaskStatus,
    depends_on: [] as string[],
    recurrence: "none" as Recurrence,
  });
  const [submitting, setSubmitting] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);

  const { connected, events } = useProjectWebSocket(params?.id ?? null);
  const { members: onlineMembers } = useProjectPresence(params?.id ?? null);
  const lastEvent = events.length ? events[events.length - 1] : null;
  const projectId = params?.id ?? "";

  async function load() {
    if (!params?.id) return;
    const [t, p] = await Promise.all([
      api.get<Task[]>(`/projects/${params.id}/tasks`),
      api.get<Project>(`/projects/${params.id}`),
    ]);
    setTasks(t.data);
    setProject(p.data);
    setLoading(false);
  }

  useEffect(() => {
    load().catch(() => setLoading(false));
  }, [params?.id]);

  useEffect(() => {
    if (!lastEvent) return;
    if (
      [
        "task.moved",
        "task.created",
        "task.updated",
        "task.imported",
        "cpm.recalculated",
        "task.bulk_deleted",
        "task.bulk_updated",
      ].includes(lastEvent.type)
    ) {
      load();
    }
  }, [lastEvent]);

  async function createTask(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post(`/projects/${params.id}/tasks`, {
        title: form.title,
        description: form.description || null,
        story_points: form.story_points,
        assignee_id: form.assignee_id || null,
        deadline: form.deadline ? new Date(form.deadline).toISOString() : null,
        depends_on: form.depends_on,
        status: form.status,
        recurrence: form.recurrence,
      });
      toast.success(t("kanban.createdToast"));
      setForm({
        title: "",
        description: "",
        story_points: 1,
        assignee_id: "",
        deadline: "",
        status: "todo" as TaskStatus,
        depends_on: [] as string[],
        recurrence: "none" as Recurrence,
      });
      setShowForm(false);
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("kanban.createError"));
    } finally {
      setSubmitting(false);
    }
  }

  async function recalculateCpm() {
    if (!params?.id) return;
    setRecalculating(true);
    try {
      const res = await api.post(`/projects/${params.id}/cpm/recalculate`);
      toast.success(
        t("kanban.cpmToast", res.data.project_duration, res.data.critical_path.length)
      );
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("kanban.cpmError"));
    } finally {
      setRecalculating(false);
    }
  }

  async function deleteTask(taskId: string) {
    if (!confirm(t("kanban.deleteConfirm"))) return;
    try {
      await api.delete(`/tasks/${taskId}`);
      toast.success(t("kanban.deletedToast"));
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("kanban.deleteError"));
    }
  }

  if (loading) return <KanbanSkeleton />;

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div className="flex items-center gap-3 text-sm text-muted">
          {connected ? (
            <span className="text-green-600 dark:text-green-400 flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              {t("kanban.realtime")}
            </span>
          ) : (
            <span className="text-faint flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-gray-300" />
              {t("kanban.disconnected")}
            </span>
          )}
          <span className="text-faint">·</span>
          <span>{t("kanban.taskCount", tasks.length)}</span>
          <span className="text-faint">·</span>
          <PresenceAvatars members={onlineMembers} />
        </div>
        <div className="flex-1 max-w-md">
          <SearchBar projectId={projectId} />
        </div>
        <div className="flex gap-2">
          <button
            onClick={recalculateCpm}
            disabled={recalculating}
            className="btn-secondary"
          >
            <RefreshCw
              className={`w-4 h-4 ${recalculating ? "animate-spin" : ""}`}
            />
            {t("kanban.recalculate")}
          </button>
          <button onClick={() => setShowForm((v) => !v)} className="btn-primary">
            <Plus className="w-4 h-4" />
            {showForm ? t("kanban.close") : t("kanban.newTask")}
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={createTask} className="card mb-4 space-y-3">
          <h3 className="font-semibold">{t("kanban.createTitle")}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="md:col-span-2">
              <label className="label">{t("kanban.titleLabel")}</label>
              <input
                required
                className="input"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </div>
            <div>
              <label className="label">{t("kanban.storyPoints")}</label>
              <input
                type="number"
                min={1}
                max={13}
                className="input"
                value={form.story_points}
                onChange={(e) =>
                  setForm({
                    ...form,
                    story_points: parseInt(e.target.value || "1"),
                  })
                }
              />
            </div>
            <div>
              <label className="label">{t("kanban.deadline")}</label>
              <input
                type="date"
                className="input"
                value={form.deadline}
                onChange={(e) => setForm({ ...form, deadline: e.target.value })}
              />
            </div>
            <div>
              <label className="label">{t("task.assignee")}</label>
              <select
                className="input"
                value={form.assignee_id}
                onChange={(e) => setForm({ ...form, assignee_id: e.target.value })}
              >
                <option value="">— {t("task.unassigned")} —</option>
                {project?.members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">{t("kanban.column")}</label>
              <select
                className="input"
                value={form.status}
                onChange={(e) =>
                  setForm({ ...form, status: e.target.value as TaskStatus })
                }
              >
                {KANBAN_COLUMNS.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="label">Phụ thuộc (Ctrl+click để chọn nhiều)</label>
              <select
                multiple
                className="input min-h-[80px]"
                value={form.depends_on}
                onChange={(e) =>
                  setForm({
                    ...form,
                    depends_on: Array.from(
                      e.target.selectedOptions,
                      (o) => o.value
                    ),
                  })
                }
              >
                {tasks.map((tk) => (
                  <option key={tk.id} value={tk.id}>
                    {tk.title}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-1">
              <label className="label">{t("kanban.repeat")}</label>
              <select
                className="input"
                value={form.recurrence}
                onChange={(e) =>
                  setForm({ ...form, recurrence: e.target.value as Recurrence })
                }
              >
                {RECURRENCE_OPTIONS.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="label">{t("kanban.description")}</label>
              <textarea
                className="input min-h-[60px]"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>
          </div>
          <button type="submit" disabled={submitting} className="btn-primary">
            {submitting ? t("common.submitting") : t("kanban.create")}
          </button>
        </form>
      )}

      <KanbanBoard
        projectId={params.id}
        project={project}
        initialTasks={tasks}
        onChange={setTasks}
        onTaskClick={setEditing}
        currentUserId={user?.id}
      />

      {tasks.length > 0 && (
        <div className="mt-6 card">
          <h3 className="font-semibold mb-2 text-sm dark:text-slate-100">Quản lý nhanh</h3>
          <div className="max-h-48 overflow-y-auto scroll-thin space-y-1">
            {tasks.map((tk) => (
              <div
                key={tk.id}
                className="flex items-center justify-between text-xs py-1 border-b border-subtle last:border-0"
              >
                <button
                  onClick={() => setEditing(tk)}
                  className="truncate flex-1 text-left hover:text-primary dark:text-slate-200"
                >
                  {tk.title}
                </button>
                <button
                  onClick={() => setEditing(tk)}
                  className="text-faint hover:text-primary ml-2"
                  title={t("common.edit")}
                >
                  ✎
                </button>
                <button
                  onClick={() => deleteTask(tk.id)}
                  className="text-red-500 hover:text-red-700 ml-2"
                  title={t("common.delete")}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {editing && user && (
        <TaskDetailPanel
          task={editing}
          members={project?.members || []}
          currentUserId={user.id}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
          onDeleted={() => {
            setEditing(null);
            load();
          }}
        />
      )}
    </div>
  );
}
