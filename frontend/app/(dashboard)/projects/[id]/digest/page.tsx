"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Mail, Send, Eye, History, Trash2, Webhook } from "lucide-react";

import { api } from "@/lib/api";
import { useI18n } from "@/components/I18nProvider";
import { Skeleton } from "@/components/Skeletons";
import { formatDate } from "@/lib/utils";
import type { DigestEmail } from "@/lib/types";

export default function DigestPage() {
  const params = useParams<{ id: string }>();
  const { t } = useI18n();
  const [preview, setPreview] = useState<DigestEmail | null>(null);
  const [history, setHistory] = useState<DigestEmail[]>([]);
  const [webhooks, setWebhooks] = useState<string[]>([]);
  const [newWebhook, setNewWebhook] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [daysAgo, setDaysAgo] = useState(7);

  async function load() {
    if (!params?.id) return;
    setLoading(true);
    try {
      const [p, h, w] = await Promise.all([
        api.get<DigestEmail>(`/projects/${params.id}/digest/preview?days_ago=${daysAgo}`),
        api.get<DigestEmail[]>(`/projects/${params.id}/digest/history`),
        api.get<{ webhooks: string[] }>(`/projects/${params.id}/webhooks`),
      ]);
      setPreview(p.data);
      setHistory(h.data);
      setWebhooks(w.data.webhooks || []);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to load digest data");
    } finally {
      setLoading(false);
    }
  }

  async function saveWebhooks(next: string[]) {
    if (!params?.id) return;
    try {
      const res = await api.put<{ webhooks: string[] }>(`/projects/${params.id}/webhooks`, {
        webhooks: next,
      });
      setWebhooks(res.data.webhooks);
      toast.success(t("digest.saveSuccess"));
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("digest.saveError"));
    }
  }

  function addWebhook() {
    const url = newWebhook.trim();
    if (!url) return;
    if (!url.startsWith("http://") && !url.startsWith("https://")) {
      toast.error(t("digest.invalidUrl"));
      return;
    }
    if (webhooks.includes(url)) {
      toast.error(t("digest.duplicateUrl"));
      return;
    }
    const next = [...webhooks, url];
    setNewWebhook("");
    saveWebhooks(next);
  }

  function removeWebhook(url: string) {
    saveWebhooks(webhooks.filter((u) => u !== url));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params?.id, daysAgo]);

  async function send() {
    if (!params?.id) return;
    setSending(true);
    try {
      const res = await api.post<DigestEmail[]>(
        `/projects/${params.id}/digest/send?days_ago=${daysAgo}`
      );
      toast.success(t("digest.sendSuccess", res.data.length));
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("digest.sendError"));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="card">
        <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
          <div>
            <h2 className="font-semibold dark:text-slate-100 flex items-center gap-2">
              <Mail className="w-4 h-4 text-primary" />
              {t("digest.title")}
            </h2>
            <p className="text-xs text-muted mt-1">{t("digest.subtitle")}</p>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted">{t("digest.timeRange")}</label>
            <select
              className="input w-32"
              value={daysAgo}
              onChange={(e) => setDaysAgo(parseInt(e.target.value))}
            >
              <option value={3}>{t("digest.days3")}</option>
              <option value={7}>{t("digest.days7")}</option>
              <option value={14}>{t("digest.days14")}</option>
              <option value={30}>{t("digest.days30")}</option>
            </select>
            <button
              onClick={send}
              disabled={sending}
              className="btn-primary"
            >
              <Send className="w-4 h-4" />
              {sending ? t("digest.sending") : t("digest.send")}
            </button>
          </div>
        </div>
        <div className="text-xs text-muted">{t("digest.smtpNote")}</div>
      </div>

      <div className="card">
        <h3 className="font-semibold mb-3 dark:text-slate-100 flex items-center gap-2">
          <Eye className="w-4 h-4 text-muted" />
          {t("digest.previewTitle")}
        </h3>
        {loading || !preview ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <div className="rounded-md border border-subtle overflow-hidden">
            <div className="bg-gray-50 dark:bg-slate-800 px-4 py-2 border-b border-subtle text-xs">
              <div>
                <span className="text-muted">From: </span>
                noreply@spm.local
              </div>
              <div>
                <span className="text-muted">To: </span>
                {preview.recipient}
              </div>
              <div>
                <span className="text-muted">Subject: </span>
                <span className="font-medium dark:text-slate-100">
                  {preview.subject}
                </span>
              </div>
              <div>
                <span className="text-muted">Date: </span>
                {formatDate(preview.sent_at, "dd/MM/yyyy HH:mm")}
              </div>
            </div>
            <pre className="p-4 text-sm text-body whitespace-pre-wrap font-sans max-h-96 overflow-y-auto scroll-thin">
              {preview.body}
            </pre>
          </div>
        )}
      </div>

      <div className="card">
        <h3 className="font-semibold mb-3 dark:text-slate-100 flex items-center gap-2">
          <Webhook className="w-4 h-4 text-muted" />
          {t("digest.webhooksTitle")}
        </h3>
        <p className="text-xs text-muted mb-3">{t("digest.webhooksHelp")}</p>
        <div className="space-y-2 mb-3">
          {webhooks.length === 0 && (
            <div className="text-sm text-muted text-center py-3 border border-dashed border-subtle rounded">
              {t("digest.webhookEmpty")}
            </div>
          )}
          {webhooks.map((url) => (
            <div
              key={url}
              className="flex items-center gap-2 p-2 border border-subtle rounded text-sm"
            >
              <code className="flex-1 truncate dark:text-slate-200 text-body">
                {url}
              </code>
              <button
                onClick={() => removeWebhook(url)}
                className="text-red-500 hover:text-red-700 p-1"
                title={t("common.delete")}
                aria-label="Remove"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            className="input"
            placeholder={t("digest.webhookPlaceholder")}
            value={newWebhook}
            onChange={(e) => setNewWebhook(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addWebhook()}
          />
          <button onClick={addWebhook} className="btn-primary">
            {t("digest.add")}
          </button>
        </div>
      </div>

      <div className="card">
        <h3 className="font-semibold mb-3 dark:text-slate-100 flex items-center gap-2">
          <History className="w-4 h-4 text-muted" />
          {t("digest.historyTitle")}
        </h3>
        {loading ? (
          <Skeleton className="h-20 w-full" />
        ) : history.length === 0 ? (
          <div className="text-sm text-muted text-center py-6">
            {t("digest.historyEmpty")}
          </div>
        ) : (
          <ul className="space-y-2">
            {history.map((d) => (
              <li
                key={d.id}
                className="flex items-center justify-between text-sm py-2 border-b border-subtle last:border-0"
              >
                <div>
                  <div className="font-medium dark:text-slate-200">
                    {d.subject}
                  </div>
                  <div className="text-xs text-muted">
                    → {d.recipient} · {formatDate(d.sent_at, "dd/MM HH:mm")}
                  </div>
                </div>
                <span
                  className={
                    d.delivery === "sent"
                      ? "badge-success"
                      : d.delivery === "preview"
                      ? "badge-primary"
                      : "badge-ghost"
                  }
                >
                  {d.delivery === "sent"
                    ? t("digest.deliverySent")
                    : d.delivery === "preview"
                    ? t("digest.deliveryPreview")
                    : d.delivery}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
