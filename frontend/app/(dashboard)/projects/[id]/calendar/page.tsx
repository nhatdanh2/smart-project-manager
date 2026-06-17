"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { Task } from "@/lib/types";
import { useI18n } from "@/components/I18nProvider";
import { CalendarView } from "@/components/CalendarView";
import { CalendarSkeleton } from "@/components/Skeletons";

export default function CalendarPage() {
  const params = useParams<{ id: string }>();
  const { t } = useI18n();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!params?.id) return;
    api
      .get<Task[]>(`/projects/${params.id}/tasks`)
      .then((res) => setTasks(res.data))
      .catch((err) => {
        setError(err?.response?.data?.detail || "Failed to load tasks");
        toast.error(err?.response?.data?.detail || "Failed to load tasks");
        setTasks([]);
      })
      .finally(() => setLoading(false));
  }, [params?.id]);

  if (loading) return <CalendarSkeleton />;

  return (
    <div className="space-y-3">
      <div>
        <h2 className="font-semibold dark:text-slate-100">{t("calendar.title")}</h2>
        <p className="text-sm text-muted">{t("calendar.subtitle")}</p>
      </div>
      {error && (
        <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded p-3">
          {error}
        </div>
      )}
      {tasks.length === 0 ? (
        <div className="card text-center text-muted py-12 border-2 border-dashed border-subtle">
          {t("calendar.noTasks")}
        </div>
      ) : (
        <CalendarView tasks={tasks} />
      )}
    </div>
  );
}
