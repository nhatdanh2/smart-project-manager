"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { History, MessageSquare, Save, Send, Trash2, UserPlus } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Checkbox } from "@/components/ui/Checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { KANBAN_COLUMNS, RECURRENCE_OPTIONS, type AuditEntry, type Member, type Recurrence, type Task, type TaskComment, type TaskStatus } from "@/lib/types";
import { useI18n } from "@/components/I18nProvider";
import { colorFromName, formatDate, initials } from "@/lib/utils";

type Tab = "details" | "comments" | "audit";

interface Props {
  task: Task;
  members: Member[];
  currentUserId: string;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
}

export function TaskDetailPanel({
  task,
  members,
  currentUserId,
  onClose,
  onSaved,
  onDeleted,
}: Props) {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("details");
  const [form, setForm] = useState({
    title: task.title,
    description: task.description || "",
    status: task.status,
    story_points: task.story_points,
    priority: task.priority,
    assignee_id: task.assignee_id || "",
    deadline: task.deadline ? task.deadline.slice(0, 10) : "",
    recurrence: (task.recurrence || "none") as Recurrence,
  });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [comments, setComments] = useState<TaskComment[]>([]);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [newComment, setNewComment] = useState("");
  const [posting, setPosting] = useState(false);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionFilter, setMentionFilter] = useState("");
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  const actionLabels: Record<string, string> = {
    created: t("actionLabels.created"),
    status_changed: t("actionLabels.status_changed"),
    bulk_status_changed: t("actionLabels.bulk_status_changed"),
    bulk_assignee_changed: t("actionLabels.bulk_assignee_changed"),
    bulk_deleted: t("actionLabels.bulk_deleted"),
    updated: t("actionLabels.updated"),
  };

  useEffect(() => {
    if (tab === "comments") {
      setCommentsLoading(true);
      api.get<TaskComment[]>(`/tasks/${task.id}/comments`)
        .then((r) => setComments(r.data))
        .catch((err) => {
          toast.error(err?.response?.data?.detail || "Failed to load comments");
          setComments([]);
        })
        .finally(() => setCommentsLoading(false));
    } else if (tab === "audit") {
      setAuditLoading(true);
      api.get<AuditEntry[]>(`/tasks/${task.id}/audit`)
        .then((r) => setAudit(r.data))
        .catch((err) => {
          toast.error(err?.response?.data?.detail || "Failed to load audit");
          setAudit([]);
        })
        .finally(() => setAuditLoading(false));
    }
  }, [tab, task.id]);

  async function save() {
    setSaving(true);
    try {
      await api.put(`/tasks/${task.id}`, {
        title: form.title,
        description: form.description || null,
        status: form.status,
        story_points: form.story_points,
        priority: form.priority,
        assignee_id: form.assignee_id || null,
        deadline: form.deadline ? new Date(form.deadline).toISOString() : null,
        recurrence: form.recurrence,
      });
      toast.success(t("taskDetail.saved"));
      onSaved();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("taskDetail.saveError"));
    } finally {
      setSaving(false);
    }
  }

  async function deleteTask() {
    if (!confirm(t("taskDetail.deleteConfirm", task.title))) return;
    setDeleting(true);
    try {
      await api.delete(`/tasks/${task.id}`);
      toast.success(t("taskDetail.deleted"));
      onDeleted();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("taskDetail.deleteError"));
    } finally {
      setDeleting(false);
    }
  }

  const mentions = useMemo(
    () => members.filter((m) => m.user_id !== currentUserId),
    [members, currentUserId]
  );
  const filteredMentions = useMemo(() => {
    if (!showMentions) return [];
    const q = mentionFilter.toLowerCase();
    return mentions
      .filter((m) => m.name.toLowerCase().includes(q) || m.email.toLowerCase().includes(q))
      .slice(0, 6);
  }, [showMentions, mentions, mentionFilter]);

  function applyMention(name: string, userId: string) {
    const ta = taRef.current;
    if (!ta) return;
    const start = ta.selectionStart ?? newComment.length;
    const end = ta.selectionEnd ?? newComment.length;
    const before = newComment.slice(0, start);
    const after = newComment.slice(end);
    const replaced = before.replace(/@[\w\u00C0-\u017F]*$/, `@${name} `);
    const next = replaced + after;
    setNewComment(next);
    setShowMentions(false);
    setMentionFilter("");
    requestAnimationFrame(() => {
      ta.focus();
      const pos = (replaced + after).length;
      ta.setSelectionRange(pos, pos);
    });
    return userId;
  }

  const [selectedMentions, setSelectedMentions] = useState<string[]>([]);

  function handleCommentChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const value = e.target.value;
    setNewComment(value);
    const ta = e.target;
    const caret = ta.selectionStart ?? value.length;
    const before = value.slice(0, caret);
    const match = before.match(/@([\w\u00C0-\u017F]*)$/);
    if (match) {
      setShowMentions(true);
      setMentionFilter(match[1]);
    } else {
      setShowMentions(false);
    }
  }

  async function postComment() {
    if (!newComment.trim()) return;
    setPosting(true);
    const mentioned: string[] = [];
    for (const m of mentions) {
      if (newComment.includes(`@${m.name}`)) {
        mentioned.push(m.user_id);
      }
    }
    const all = Array.from(new Set([...mentioned, ...selectedMentions]));
    try {
      const res = await api.post<TaskComment>(`/tasks/${task.id}/comments`, {
        body: newComment.trim(),
        mentions: all,
      });
      setComments((prev) => [...prev, res.data]);
      setNewComment("");
      setSelectedMentions([]);
      toast.success(t("taskDetail.sent"));
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("taskDetail.sendError"));
    } finally {
      setPosting(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{task.title}</DialogTitle>
          <DialogDescription>{t("taskDetail.description")}</DialogDescription>
        </DialogHeader>

        <div className="flex border-b border-subtle">
          {(
            [
              { id: "details", label: t("taskDetail.tabs.details") },
              { id: "comments", label: t("taskDetail.tabs.commentsLabel", comments.length) },
              { id: "audit", label: t("taskDetail.tabs.audit") },
            ] as { id: Tab; label: string }[]
          ).map((tb) => (
            <button
              key={tb.id}
              onClick={() => setTab(tb.id)}
              className={`px-4 py-2 text-sm border-b-2 -mb-px ${
                tab === tb.id
                  ? "border-primary text-primary font-medium"
                  : "border-transparent text-muted hover:text-body"
              }`}
            >
              {tb.label}
            </button>
          ))}
        </div>

        {tab === "details" && (
          <div className="space-y-3 max-h-[60vh] overflow-y-auto scroll-thin">
            <div>
              <Label>{t("taskDetail.fields.title")}</Label>
              <Input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </div>
            <div>
              <Label>{t("taskDetail.fields.description")}</Label>
              <Textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>{t("taskDetail.fields.status")}</Label>
                <Select
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
                </Select>
              </div>
              <div>
                <Label>{t("taskDetail.fields.storyPoints")}</Label>
                <Input
                  type="number"
                  min={1}
                  max={13}
                  value={form.story_points}
                  onChange={(e) =>
                    setForm({ ...form, story_points: parseInt(e.target.value || "1") })
                  }
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>{t("taskDetail.fields.priority")}</Label>
                <Input
                  type="number"
                  value={form.priority}
                  onChange={(e) =>
                    setForm({ ...form, priority: parseInt(e.target.value || "100") })
                  }
                />
              </div>
              <div>
                <Label>{t("taskDetail.fields.assignee")}</Label>
                <Select
                  value={form.assignee_id}
                  onChange={(e) => setForm({ ...form, assignee_id: e.target.value })}
                >
                  <option value="">{t("taskDetail.fields.unassigned")}</option>
                  {members.map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.name}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div>
              <Label>{t("taskDetail.fields.deadline")}</Label>
              <Input
                type="date"
                value={form.deadline}
                onChange={(e) => setForm({ ...form, deadline: e.target.value })}
              />
            </div>
            <div>
              <Label>{t("taskDetail.fields.recurrence")}</Label>
              <Select
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
              </Select>
              {form.recurrence !== "none" && form.deadline && (
                <p className="text-xs text-muted mt-1">
                  {t("taskDetail.fields.recurrenceHelp")}
                </p>
              )}
            </div>
            {task.is_critical && (
              <div className="rounded-md bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300 flex items-center gap-2">
                {t("taskDetail.critical", task.slack ?? 0)}
              </div>
            )}
          </div>
        )}

        {tab === "comments" && (
          <div className="space-y-3 max-h-[60vh] overflow-y-auto scroll-thin">
            {commentsLoading && comments.length === 0 && (
              <div className="text-sm text-muted text-center py-4">{t("notification.loading")}</div>
            )}
            {!commentsLoading && comments.length === 0 && (
              <div className="text-sm text-muted text-center py-4">
                {t("taskDetail.noComments")}
              </div>
            )}
            {comments.map((c) => {
              const color = colorFromName(c.user_name || "?");
              return (
                <div key={c.id} className="flex items-start gap-3">
                  <span
                    className="w-8 h-8 rounded-full text-white text-xs font-semibold flex items-center justify-center flex-shrink-0"
                    style={{ background: color }}
                  >
                    {initials(c.user_name || "?")}
                  </span>
                  <div className="flex-1 bg-gray-50 dark:bg-slate-800/50 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-sm dark:text-slate-100">
                        {c.user_name || t("taskDetail.unknownUser")}
                      </span>
                      <span className="text-xs text-muted">
                        {formatDate(c.created_at, "dd/MM HH:mm")}
                      </span>
                    </div>
                    <p className="text-sm text-body whitespace-pre-wrap">{c.body}</p>
                    {c.mentions.length > 0 && (
                      <div className="flex items-center gap-1 mt-1">
                        <UserPlus className="w-3 h-3 text-muted" />
                        <span className="text-xs text-muted">
                          {t("taskDetail.mentionFooter", c.mentions.length)}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
            <div className="pt-2 border-t border-subtle">
              <div className="relative">
                <Textarea
                  ref={taRef}
                  placeholder={t("taskDetail.commentPlaceholder")}
                  value={newComment}
                  onChange={handleCommentChange}
                  className="min-h-[60px]"
                />
                {showMentions && filteredMentions.length > 0 && (
                  <Card className="absolute z-10 mt-1 p-1 max-h-48 overflow-y-auto scroll-thin w-64">
                    {filteredMentions.map((m) => (
                      <button
                        key={m.user_id}
                        onClick={() => applyMention(m.name, m.user_id)}
                        className="w-full text-left px-2 py-1.5 text-sm rounded hover:bg-gray-100 dark:hover:bg-slate-800 flex items-center gap-2"
                      >
                        <span
                          className="w-6 h-6 rounded-full text-white text-[10px] font-semibold flex items-center justify-center"
                          style={{ background: colorFromName(m.name) }}
                        >
                          {initials(m.name)}
                        </span>
                        <div>
                          <div className="font-medium dark:text-slate-100">{m.name}</div>
                          <div className="text-xs text-muted">{m.email}</div>
                        </div>
                      </button>
                    ))}
                  </Card>
                )}
              </div>
              <div className="flex justify-end mt-2">
                <Button onClick={postComment} disabled={posting || !newComment.trim()}>
                  <Send className="w-4 h-4" />
                  {posting ? t("taskDetail.sending") : t("taskDetail.send")}
                </Button>
              </div>
            </div>
          </div>
        )}

        {tab === "audit" && (
          <div className="max-h-[60vh] overflow-y-auto scroll-thin space-y-1">
            {auditLoading && audit.length === 0 && (
              <div className="text-sm text-muted text-center py-4">{t("notification.loading")}</div>
            )}
            {!auditLoading && audit.length === 0 && (
              <div className="text-sm text-muted text-center py-4">
                {t("taskDetail.noAudit")}
              </div>
            )}
            {audit.map((a) => {
              const color = a.user_name ? colorFromName(a.user_name) : "#9CA3AF";
              return (
                <div
                  key={a.id}
                  className="flex items-start gap-3 p-2 border-b border-subtle last:border-0"
                >
                  <span
                    className="w-7 h-7 rounded-full text-white text-[10px] font-semibold flex items-center justify-center flex-shrink-0"
                    style={{ background: color }}
                  >
                    {a.user_name ? initials(a.user_name) : "·"}
                  </span>
                  <div className="flex-1">
                    <div className="text-sm text-body">
                      <span className="font-medium dark:text-slate-100">
                        {a.user_name || t("taskDetail.systemUser")}
                      </span>{" "}
                      {actionLabels[a.action] || a.action}
                      {a.old_value && a.new_value && (
                        <span className="text-muted">
                          : <code className="text-xs">{a.old_value}</code> →{" "}
                          <code className="text-xs">{a.new_value}</code>
                        </span>
                      )}
                      {a.new_value && !a.old_value && (
                        <span className="text-muted">
                          : <code className="text-xs">{a.new_value}</code>
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-muted mt-0.5">
                      {formatDate(a.created_at, "dd/MM/yyyy HH:mm:ss")}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <DialogFooter className="mt-4">
          {tab === "details" && (
            <>
              <Button variant="danger" onClick={deleteTask} disabled={deleting}>
                <Trash2 className="w-4 h-4" />
                {deleting ? t("taskDetail.deleting") : t("taskDetail.delete")}
              </Button>
              <div className="flex-1" />
              <Button variant="secondary" onClick={onClose}>
                {t("taskDetail.close")}
              </Button>
              <Button onClick={save} disabled={saving}>
                <Save className="w-4 h-4" />
                {saving ? t("taskDetail.saving") : t("taskDetail.save")}
              </Button>
            </>
          )}
          {tab !== "details" && (
            <Button variant="secondary" onClick={onClose}>
              {t("taskDetail.close")}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
