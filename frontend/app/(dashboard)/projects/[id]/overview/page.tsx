"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Download, FileText } from "lucide-react";

import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { AIReport, Project, ProjectSummary, Task } from "@/lib/types";
import { useI18n } from "@/components/I18nProvider";
import { DependencyGraph } from "@/components/DependencyGraph";
import { exportReportToPdf } from "@/lib/pdfExport";

export default function ProjectOverviewPage() {
  const params = useParams<{ id: string }>();
  const { t } = useI18n();
  const [summary, setSummary] = useState<ProjectSummary | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [reports, setReports] = useState<AIReport[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!params?.id) return;
    const [s, t, r, p] = await Promise.all([
      api.get<ProjectSummary>(`/projects/${params.id}/summary`),
      api.get<Task[]>(`/projects/${params.id}/tasks`),
      api.get<AIReport[]>(`/projects/${params.id}/reports`),
      api.get<Project>(`/projects/${params.id}`),
    ]);
    setSummary(s.data);
    setTasks(t.data);
    setReports(r.data);
    setProject(p.data);
  }

  useEffect(() => {
    load().catch(() => {});
  }, [params?.id]);

  async function generateReport() {
    if (!params?.id) return;
    setGenerating(true);
    setError(null);
    try {
      await api.post(`/projects/${params.id}/reports/generate`);
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || t("overview.generateError"));
    } finally {
      setGenerating(false);
    }
  }

  if (!summary) return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[0,1,2,3].map(i => <div key={i} className="card animate-pulse h-20" />)}
      </div>
      <div className="card animate-pulse h-32" />
    </div>
  );

  const critical = tasks.filter((tk) => tk.is_critical);
  const riskPct = ((summary.cpm_delay_risk ?? 0) * 100) | 0;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard title={t("overview.totalTasks")} value={summary.total_tasks} />
        <StatCard
          title={t("overview.completed")}
          value={summary.completed_tasks}
          tone="success"
        />
        <StatCard
          title={t("overview.overdue")}
          value={summary.overdue_tasks}
          tone={summary.overdue_tasks > 0 ? "danger" : "ghost"}
        />
        <StatCard
          title={t("overview.cpmDuration")}
          value={summary.cpm_project_duration ?? "—"}
          subtitle={t("overview.cpmRisk", riskPct)}
        />
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h2 className="font-semibold dark:text-slate-100">{t("overview.aiReports")}</h2>
          <button
            onClick={generateReport}
            disabled={generating}
            className="btn-primary"
          >
            {generating ? t("overview.generating") : t("overview.generate")}
          </button>
        </div>
        {error && <div className="text-sm text-red-600 mb-2">{error}</div>}
        {reports.length === 0 ? (
          <div className="text-sm text-muted">{t("overview.noReports")}</div>
        ) : (
          <div className="space-y-3">
            {reports.map((r) => (
              <div
                key={r.id}
                className="border border-subtle rounded-md p-3"
              >
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="font-medium text-sm dark:text-slate-100 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-muted" />
                    {t("overview.reportTitle", formatDate(r.created_at, "dd/MM/yyyy HH:mm"))}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        if (summary && project) {
                          try {
                            exportReportToPdf({ project, summary, report: r });
                          } catch (err) {
                            console.error(err);
                          }
                        }
                      }}
                      className="btn-secondary text-xs"
                      title={t("overview.downloadPdf")}
                    >
                      <Download className="w-3.5 h-3.5" />
                      PDF
                    </button>
                    <details>
                      <summary className="cursor-pointer text-xs text-primary hover:underline list-none">
                        {t("overview.viewDetail")}
                      </summary>
                    </details>
                  </div>
                </div>
                <pre className="text-sm text-body whitespace-pre-wrap mt-3 font-sans">
                  {r.report_text}
                </pre>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="font-semibold mb-3 dark:text-slate-100">
          {t("overview.criticalPath", critical.length)}
        </h2>
        {critical.length === 0 ? (
          <div className="text-sm text-muted">{t("overview.noCritical")}</div>
        ) : (
          <ul className="space-y-2 text-sm">
            {critical.map((tk) => (
              <li
                key={tk.id}
                className="flex items-center justify-between border-l-4 border-red-500 pl-3 py-1"
              >
                <div>
                  <div className="font-medium dark:text-slate-100">{tk.title}</div>
                  <div className="text-xs text-muted">
                    {t("overview.taskMeta", t("overview.assigneeOrUnassigned", tk.assignee_name), tk.story_points, tk.slack ?? 0)}
                  </div>
                </div>
                <span className="badge-critical">{t("overview.critical")}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card">
        <h2 className="font-semibold mb-3 dark:text-slate-100">{t("overview.depGraph")}</h2>
        <p className="text-xs text-muted mb-3">{t("overview.depGraphDesc")}</p>
        <DependencyGraph tasks={tasks} />
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  subtitle,
  tone = "default",
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  tone?: "default" | "success" | "danger" | "ghost";
}) {
  const toneClass = {
    success: "text-green-700 dark:text-green-300",
    danger: "text-red-600 dark:text-red-400",
    ghost: "text-muted",
    default: "text-heading",
  }[tone];
  return (
    <div className="card">
      <div className="text-xs text-muted uppercase tracking-wide">{title}</div>
      <div className={`text-3xl font-semibold mt-1 ${toneClass}`}>{value}</div>
      {subtitle && <div className="text-xs text-muted mt-1">{subtitle}</div>}
    </div>
  );
}
