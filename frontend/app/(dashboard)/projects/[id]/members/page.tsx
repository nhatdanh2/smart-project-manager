"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { UserPlus, X } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "@/lib/api";
import type { Member, Project, User } from "@/lib/types";
import { colorFromName } from "@/lib/utils";
import { useI18n } from "@/components/I18nProvider";
import { ActivityHeatMap } from "@/components/ActivityHeatMap";
import { CardSkeleton } from "@/components/Skeletons";

export default function MembersPage() {
  const params = useParams<{ id: string }>();
  const { t } = useI18n();
  const [members, setMembers] = useState<Member[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [showInvite, setShowInvite] = useState(false);

  async function load() {
    if (!params?.id) return;
    const [m, p] = await Promise.all([
      api.get<Member[]>(`/projects/${params.id}/contributions`),
      api.get<Project>(`/projects/${params.id}`),
    ]);
    setMembers(m.data);
    setProject(p.data);
    setLoading(false);
  }

  useEffect(() => {
    load().catch(() => setLoading(false));
  }, [params?.id]);

  async function removeMember(userId: string, name: string) {
    if (!confirm(t("members.removeConfirm", name))) return;
    try {
      await api.delete(`/projects/${params.id}/members/${userId}`);
      toast.success(t("members.removedToast", name));
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("members.removeError"));
    }
  }

  if (loading) return <CardSkeleton />;

  const radarData = members
    .filter((m) => m.contribution_percent !== null && m.contribution_percent !== undefined)
    .map((m) => ({
      name: m.name,
      contribution: Math.max(0, Math.min(100, m.contribution_percent ?? 0)),
    }));

  const barData = members.map((m) => ({
    name: m.name,
    percent: Math.max(0, Math.min(100, m.contribution_percent ?? 0)),
  }));

  const totalPct = members.reduce((s, m) => s + (m.contribution_percent ?? 0), 0).toFixed(0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="text-sm text-muted">
          {t("members.countLine", members.length, totalPct)}
        </div>
        <button
          onClick={() => setShowInvite(true)}
          className="btn-primary"
        >
          <UserPlus className="w-4 h-4" />
          {t("members.invite")}
        </button>
      </div>

      <ActivityHeatMap
        projectId={params.id}
        members={members.map((m) => ({ user_id: m.user_id, name: m.name }))}
      />

      <div className="card">
        <h2 className="font-semibold mb-2 dark:text-slate-100">
          {t("members.contributionBreakdown")}
        </h2>
        <p className="text-sm text-muted mb-4">{t("members.formula")}</p>
        <div style={{ width: "100%", height: 300 }}>
          <ResponsiveContainer>
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis unit="%" />
              <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
              <Bar dataKey="percent" name={t("members.contribution")}>
                {barData.map((m, i) => (
                  <Cell key={i} fill={colorFromName(m.name)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <h2 className="font-semibold mb-4 dark:text-slate-100">{t("members.detailTitle")}</h2>
        <div className="space-y-3">
          {members.map((m) => {
            const pct = m.contribution_percent ?? 0;
            const isGhost = pct < 15;
            const isOverworked = pct > 40;
            return (
              <div
                key={m.user_id}
                className={`p-3 border rounded-md ${
                  isGhost
                    ? "border-gray-300 bg-gray-50 dark:border-slate-700 dark:bg-slate-800/40"
                    : "border-subtle"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <span
                      className="w-8 h-8 rounded-full text-white text-xs font-semibold flex items-center justify-center"
                      style={{ background: colorFromName(m.name) }}
                    >
                      {m.name
                        .split(/\s+/)
                        .map((s) => s[0])
                        .slice(0, 2)
                        .join("")
                        .toUpperCase()}
                    </span>
                    <div>
                      <div className="font-medium dark:text-slate-100">
                        {m.name}{" "}
                        {m.role === "leader" && (
                          <span className="badge-primary ml-1">{t("members.leader")}</span>
                        )}
                        {isGhost && <span className="badge-ghost ml-1">{t("members.ghost")}</span>}
                        {isOverworked && (
                          <span className="badge-warning ml-1">{t("members.overworked")}</span>
                        )}
                      </div>
                      <div className="text-xs text-muted">{m.email}</div>
                    </div>
                  </div>
                  <div className="text-right flex items-center gap-2">
                    <div>
                      <div className="text-2xl font-semibold dark:text-slate-100">{pct.toFixed(1)}%</div>
                      <div className="text-xs text-muted">{t("members.contributionLabel")}</div>
                    </div>
                    {m.role !== "leader" && (
                      <button
                        onClick={() => removeMember(m.user_id, m.name)}
                        className="text-faint hover:text-red-500 text-xs ml-2"
                        title={t("members.removeFromProject")}
                      >
                        ✕
                      </button>
                    )}
                  </div>
                </div>
                <div className="w-full bg-gray-200 dark:bg-slate-700 rounded-full h-2">
                  <div
                    className="h-2 rounded-full"
                    style={{
                      width: `${Math.min(100, pct)}%`,
                      background: colorFromName(m.name),
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="card">
        <h2 className="font-semibold mb-4">{t("members.radarTitle")}</h2>
        {radarData.length === 0 ? (
          <div className="text-sm text-muted text-center py-12 border-2 border-dashed border-subtle rounded-md">
            {t("members.noRadar")}
          </div>
        ) : (
          <div style={{ width: "100%", height: 320 }}>
            <ResponsiveContainer>
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="name" />
                <PolarRadiusAxis domain={[0, 100]} />
                <Radar
                  name={t("members.contribution")}
                  dataKey="contribution"
                  stroke="#6366F1"
                  fill="#6366F1"
                  fillOpacity={0.4}
                />
                <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
                <Legend />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {showInvite && project && (
        <InviteMemberModal
          projectId={project.id}
          existingMemberIds={project.members.map((m) => m.user_id)}
          onClose={() => setShowInvite(false)}
          onAdded={() => {
            setShowInvite(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function InviteMemberModal({
  projectId,
  existingMemberIds,
  onClose,
  onAdded,
}: {
  projectId: string;
  existingMemberIds: string[];
  onClose: () => void;
  onAdded: () => void;
}) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [users, setUsers] = useState<User[]>([]);
  const [searching, setSearching] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);

  async function search() {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const res = await api.get<User[]>(`/users/search?q=${encodeURIComponent(query)}`);
      setUsers(res.data);
    } catch {
      setUsers([]);
    } finally {
      setSearching(false);
    }
  }

  async function invite(userId: string) {
    setAdding(userId);
    try {
      await api.post(`/projects/${projectId}/members`, {
        user_id: userId,
        role: "member",
      });
      toast.success(t("members.invitedToast"));
      onAdded();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("members.inviteError"));
    } finally {
      setAdding(null);
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-slate-900 rounded-lg max-w-md w-full"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-5 border-b border-subtle">
          <h3 className="font-semibold text-lg dark:text-slate-100">
            {t("members.modalTitle")}
          </h3>
          <button onClick={onClose} className="text-faint hover:text-body">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-5 space-y-3">
          <div className="flex gap-2">
            <input
              className="input"
              placeholder={t("members.searchPlaceholder")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
            />
            <button onClick={search} disabled={searching} className="btn-primary">
              {searching ? "..." : t("members.find")}
            </button>
          </div>
          <div className="max-h-60 overflow-y-auto scroll-thin space-y-1">
            {users.length === 0 && !searching && (
              <div className="text-sm text-muted text-center py-4">
                {t("members.searchHint")}
              </div>
            )}
            {users.map((u) => {
              const isMember = existingMemberIds.includes(u.id);
              return (
                <div
                  key={u.id}
                  className="flex items-center justify-between p-2 hover:bg-gray-50 dark:hover:bg-slate-800 rounded"
                >
                  <div>
                    <div className="text-sm font-medium dark:text-slate-100">{u.name}</div>
                    <div className="text-xs text-muted">{u.email}</div>
                  </div>
                  {isMember ? (
                    <span className="badge-ghost text-xs">{t("members.alreadyMember")}</span>
                  ) : (
                    <button
                      onClick={() => invite(u.id)}
                      disabled={adding === u.id}
                      className="btn-primary text-xs px-3 py-1"
                    >
                      {adding === u.id ? "..." : t("members.inviteBtn")}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
