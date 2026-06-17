"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { Project, ProjectSummary, Task } from "@/lib/types";
import { useI18n } from "@/components/I18nProvider";
import { InstructorSkeleton } from "@/components/Skeletons";
import { formatDate } from "@/lib/utils";

interface ProjectWithStats {
  project: Project;
  summary: ProjectSummary;
  ghostMembers: string[];
}

export default function InstructorDashboard() {
  const { t } = useI18n();
  const [data, setData] = useState<ProjectWithStats[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const projectsRes = await api.get<Project[]>("/projects");
        const projects = projectsRes.data;
        const enriched = await Promise.all(
          projects.map(async (p) => {
            const [s, tasks] = await Promise.all([
              api.get<ProjectSummary>(`/projects/${p.id}/summary`),
              api.get<Task[]>(`/projects/${p.id}/tasks`),
            ]);
            const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
            const ghosts: string[] = [];
            for (const m of p.members) {
              const memberTasks = tasks.data.filter((tk) => tk.assignee_id === m.user_id);
              const lastUpdate = memberTasks
                .map((tk) => tk.completed_at || tk.deadline || tk.created_at)
                .filter(Boolean)
                .map((d) => new Date(d!).getTime())
                .sort((a, b) => b - a)[0];
              if (!lastUpdate || lastUpdate < sevenDaysAgo) {
                if (memberTasks.length === 0 || lastUpdate === undefined) ghosts.push(m.name);
                else if (lastUpdate < sevenDaysAgo) ghosts.push(m.name);
              }
            }
            return { project: p, summary: s.data, ghostMembers: ghosts };
          })
        );
        setData(enriched);
        setError(null);
      } catch (err: any) {
        toast.error(err?.response?.data?.detail || "Failed to load dashboard");
        setData([]);
        setError(err?.response?.data?.detail || "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <InstructorSkeleton />;

  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-semibold mb-1 dark:text-slate-100">
        {t("instructor.title")}
      </h1>
      <p className="text-sm text-muted mb-6">{t("instructor.subtitle")}</p>

      {error && (
        <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded p-3 mb-4">
          {error}
        </div>
      )}

      {!data || data.length === 0 ? (
        <div className="card text-muted text-center py-12 border-2 border-dashed border-subtle">
          {t("instructor.noProjects")}
        </div>
      ) : (
        <div className="space-y-4">
          {data.map(({ project, summary, ghostMembers }) => {
            const risk = summary.cpm_delay_risk ?? 0;
            return (
              <Link
                key={project.id}
                href={`/projects/${project.id}`}
                className="card hover:shadow-md transition-shadow block"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="font-semibold text-lg dark:text-slate-100">
                      {project.title}
                    </h3>
                    <p className="text-xs text-muted">
                      {t("instructor.deadline")}: {formatDate(project.deadline)}
                    </p>
                  </div>
                  <RiskBadge risk={risk} tHigh={t("instructor.riskHigh")} tMedium={t("instructor.riskMedium")} tLow={t("instructor.riskLow")} />
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm mt-3">
                  <Stat label={t("instructor.tasks")} value={`${summary.completed_tasks}/${summary.total_tasks}`} />
                  <Stat
                    label={t("instructor.overdue")}
                    value={summary.overdue_tasks}
                    tone={summary.overdue_tasks > 0 ? "danger" : "default"}
                  />
                  <Stat label={t("instructor.cpm")} value={t("instructor.cpmValue", summary.cpm_project_duration)} />
                  <Stat label={t("instructor.members")} value={summary.project.members.length} />
                </div>
                {ghostMembers.length > 0 && (
                  <div className="mt-3 text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
                    {t("instructor.ghostWarning", ghostMembers.join(", "))}
                  </div>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone = "default" }: { label: string; value: any; tone?: string }) {
  const cls = tone === "danger" ? "text-red-600" : "text-heading";
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className={`font-semibold ${cls}`}>{value}</div>
    </div>
  );
}

function RiskBadge({ risk, tHigh, tMedium, tLow }: { risk: number; tHigh: string; tMedium: string; tLow: string }) {
  if (risk >= 0.7) return <span className="badge-critical">{tHigh}</span>;
  if (risk >= 0.3) return <span className="badge-warning">{tMedium}</span>;
  return <span className="badge-success">{tLow}</span>;
}
