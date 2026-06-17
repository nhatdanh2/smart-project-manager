"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, Users } from "lucide-react";

import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/components/I18nProvider";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { Input, Textarea } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";

export default function ProjectsPage() {
  const { t } = useI18n();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 30);
    return d.toISOString().slice(0, 10);
  });
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  async function load() {
    const res = await api.get<Project[]>("/projects");
    setProjects(res.data);
  }

  useEffect(() => {
    load().catch(() => setProjects([]));
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setCreating(true);
    try {
      const res = await api.post<Project>("/projects", {
        title,
        description: description || null,
        deadline: new Date(deadline).toISOString(),
      });
      toast.success(t("projects.createdToast", res.data.title));
      setTitle("");
      setDescription("");
      setShowForm(false);
      await load();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || t("projects.createError");
      setError(msg);
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  }

  async function deleteProject(projectId: string, projectTitle: string, e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(t("projects.deleteConfirm", projectTitle))) return;
    try {
      await api.delete(`/projects/${projectId}`);
      toast.success(t("projects.deletedToast"));
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("projects.deleteError"));
    }
  }

  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold dark:text-slate-100">
            {t("projects.myProjects")}
          </h1>
          <p className="text-sm text-muted">{t("projects.myProjectsDesc")}</p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)}>
          <Plus className="w-4 h-4" />
          {showForm ? t("projects.close") : t("projects.newProject")}
        </Button>
      </div>

      {showForm && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">{t("projects.createTitle")}</CardTitle>
            <CardDescription>{t("projects.createDesc")}</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onCreate} className="space-y-3">
              <div>
                <Label htmlFor="p-title">{t("projects.nameLabel")}</Label>
                <Input
                  id="p-title"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="p-desc">{t("projects.descriptionLabel")}</Label>
                <Textarea
                  id="p-desc"
                  className="min-h-[80px]"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="p-dl">{t("projects.deadlineLabel")}</Label>
                <Input
                  id="p-dl"
                  type="date"
                  required
                  value={deadline}
                  onChange={(e) => setDeadline(e.target.value)}
                />
              </div>
              {error && <div className="text-sm text-red-600">{error}</div>}
              <Button type="submit" disabled={creating}>
                {creating ? t("projects.creating") : t("projects.create")}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {projects === null && <div className="text-muted">{t("common.loading")}</div>}
      {projects && projects.length === 0 && (
        <Card className="text-center text-muted">
          {t("projects.noProjects")}
        </Card>
      )}
      {projects && projects.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p) => (
            <Link
              key={p.id}
              href={`/projects/${p.id}`}
              className="block hover:shadow-md transition-shadow group relative"
            >
              <Card>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={(e) => deleteProject(p.id, p.title, e)}
                  className="absolute top-2 right-2 text-faint hover:text-red-500 opacity-0 group-hover:opacity-100"
                  title={t("projects.deleteTitle")}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
                <div className="flex items-start justify-between mb-2 pr-8">
                  <h3 className="font-semibold text-lg dark:text-slate-100">
                    {p.title}
                  </h3>
                  <Badge
                    variant={
                      p.status === "active"
                        ? "success"
                        : p.status === "overdue"
                        ? "danger"
                        : "secondary"
                    }
                  >
                    {p.status}
                  </Badge>
                </div>
                <p className="text-sm text-body line-clamp-2 mb-3 min-h-[2.5rem]">
                  {p.description || t("projects.noDescription")}
                </p>
                <div className="flex items-center justify-between text-xs text-muted">
                  <span>
                    {t("projects.deadlineLabel")}: {formatDate(p.deadline)}
                  </span>
                  <span className="flex items-center gap-1">
                    <Users className="w-3 h-3" />
                    {p.members.length}
                  </span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
