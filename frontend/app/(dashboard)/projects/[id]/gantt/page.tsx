"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { RefreshCw } from "lucide-react";

import { api } from "@/lib/api";
import type { Task, TaskStatus } from "@/lib/types";
import { useI18n } from "@/components/I18nProvider";
import { GanttChart } from "@/components/GanttChart";
import { CardSkeleton } from "@/components/Skeletons";
import { KANBAN_COLUMNS } from "@/lib/types";

export default function GanttPage() {
  const params = useParams<{ id: string }>();
  const { t } = useI18n();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [recalculating, setRecalculating] = useState(false);
  const [selected, setSelected] = useState<Task | null>(null);

  async function load() {
    if (!params?.id) return;
    try {
      const res = await api.get<Task[]>(`/projects/${params.id}/tasks`);
      setTasks(res.data);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to load tasks");
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [params?.id]);

  async function recalculate() {
    if (!params?.id) return;
    setRecalculating(true);
    try {
      const res = await api.post(`/projects/${params.id}/cpm/recalculate`);
      toast.success(t("gantt.cpmToast", res.data.project_duration, res.data.critical_path.length));
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("gantt.cpmError"));
    } finally {
      setRecalculating(false);
    }
  }

  if (loading) return <CardSkeleton />;

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <p className="text-sm text-muted max-w-2xl">{t("gantt.helpText")}</p>
        <button
          onClick={recalculate}
          disabled={recalculating}
          className="btn-secondary"
        >
          <RefreshCw className={`w-4 h-4 ${recalculating ? "animate-spin" : ""}`} />
          {t("gantt.recalculate")}
        </button>
      </div>

      {tasks.length === 0 ? (
        <div className="card text-center text-muted py-12 border-2 border-dashed border-subtle">
          {t("gantt.noTasks")}
        </div>
      ) : (
        <GanttChart tasks={tasks} onTaskClick={setSelected} />
      )}

      {selected && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 rounded-lg max-w-md w-full p-5">
            <div className="flex items-start justify-between mb-3">
              <h3 className="font-semibold text-lg dark:text-slate-100">{selected.title}</h3>
              <button
                onClick={() => setSelected(null)}
                className="text-faint hover:text-body"
                aria-label="Close"
              >
                ✕
              </button>
            </div>
            <div className="space-y-2 text-sm">
              <Field label={t("gantt.fields.status")}>
                <span className="badge-primary">
                  {KANBAN_COLUMNS.find((c) => c.id === selected.status)?.title || selected.status}
                </span>
              </Field>
              <Field label={t("gantt.fields.assignee")}>
                {selected.assignee_name || "—"}
              </Field>
              <Field label={t("gantt.fields.storyPoints")}>
                {selected.story_points}
              </Field>
              <Field label={t("gantt.fields.duration")}>
                {t("gantt.fields.durationValue", selected.early_start, selected.early_finish)}
              </Field>
              <Field label={t("gantt.fields.slack")}>
                {t("gantt.fields.slackValue", selected.slack ?? 0)}{" "}
                {selected.is_critical && (
                  <span className="badge-critical ml-1">{t("gantt.fields.critical")}</span>
                )}
              </Field>
              {selected.deadline && (
                <Field label={t("gantt.fields.deadline")}>
                  {new Date(selected.deadline).toLocaleDateString(
                    typeof window !== "undefined" && document.documentElement.lang === "en" ? "en-US" : "vi-VN"
                  )}
                </Field>
              )}
              {selected.depends_on.length > 0 && (
                <Field label={t("gantt.fields.dependsOn")}>
                  {t("gantt.fields.dependsOnValue", selected.depends_on.length)}
                </Field>
              )}
              {selected.description && (
                <div>
                  <div className="text-xs text-muted mb-1">{t("gantt.fields.description")}</div>
                  <p className="text-sm text-body whitespace-pre-wrap">
                    {selected.description}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="text-xs text-muted uppercase tracking-wide min-w-[100px]">
        {label}
      </div>
      <div className="text-sm text-heading text-right flex-1">{children}</div>
    </div>
  );
}
