"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Project, ProjectSummary } from "@/lib/types";
import { useI18n } from "@/components/I18nProvider";

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const params = useParams<{ id: string }>();
  const pathname = usePathname();
  const { t } = useI18n();
  const [project, setProject] = useState<Project | null>(null);
  const [summary, setSummary] = useState<ProjectSummary | null>(null);

  useEffect(() => {
    if (!params?.id) return;
    Promise.all([
      api.get<Project>(`/projects/${params.id}`),
      api.get<ProjectSummary>(`/projects/${params.id}/summary`),
    ])
      .then(([p, s]) => {
        setProject(p.data);
        setSummary(s.data);
      })
      .catch(() => setProject(null));
  }, [params?.id]);

  const TABS = [
    { id: "overview", label: t("tabs.overview") },
    { id: "kanban", label: t("tabs.kanban") },
    { id: "gantt", label: t("tabs.gantt") },
    { id: "calendar", label: t("tabs.calendar") },
    { id: "members", label: t("tabs.members") },
    { id: "meeting", label: t("tabs.meeting") },
    { id: "digest", label: t("tabs.digest") },
    { id: "webhooks", label: t("tabs.webhooks") },
  ] as const;

  const activeTab =
    TABS.find((tab) => pathname?.endsWith(`/${tab.id}`))?.id || "overview";

  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-7xl mx-auto">
      <div className="mb-6">
        <Link
          href="/projects"
          className="text-sm text-gray-500 hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-200"
        >
          {t("projects.backToList")}
        </Link>
        {project ? (
          <>
            <h1 className="text-2xl font-semibold mt-2 dark:text-slate-100">
              {project.title}
            </h1>
            <p className="text-sm text-gray-500 dark:text-slate-400">
              {project.description || t("projects.noDescription")}
            </p>
            {summary && (
              <div className="flex gap-4 mt-3 text-xs text-gray-600 dark:text-slate-300 flex-wrap">
                <span>{t("projectHeader.totalTasks", summary.total_tasks)}</span>
                <span>{t("projectHeader.completed", summary.completed_tasks)}</span>
                <span>{t("projectHeader.overdue", summary.overdue_tasks)}</span>
                {summary.cpm_delay_risk !== null && summary.cpm_delay_risk !== undefined && (
                  <span>
                    {t(
                      "projectHeader.cpmLine",
                      summary.cpm_project_duration ?? 0,
                      (summary.cpm_delay_risk * 100).toFixed(0)
                    )}{" "}
                    <span
                      className={
                        summary.cpm_delay_risk >= 0.7
                          ? "text-red-600 font-medium"
                          : summary.cpm_delay_risk >= 0.3
                          ? "text-yellow-700 font-medium"
                          : "text-green-700 font-medium"
                      }
                    >
                      {(summary.cpm_delay_risk * 100).toFixed(0)}%
                    </span>
                  </span>
                )}
              </div>
            )}
          </>
        ) : (
          <div className="text-gray-500 dark:text-slate-400 mt-2">
            {t("projectHeader.loading")}
          </div>
        )}
      </div>

      <div className="flex border-b border-gray-200 dark:border-slate-800 mb-6 overflow-x-auto scroll-thin">
        {TABS.map((tab) => (
          <Link
            key={tab.id}
            href={`/projects/${params.id}/${tab.id}`}
            className={cn(
              "px-4 py-2 text-sm border-b-2 -mb-px whitespace-nowrap",
              activeTab === tab.id
                ? "border-primary text-primary font-medium"
                : "border-transparent text-gray-500 hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-200"
            )}
          >
            {tab.label}
          </Link>
        ))}
      </div>

      {children}
    </div>
  );
}
