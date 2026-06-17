"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { useI18n } from "@/components/I18nProvider";
import { Skeleton } from "@/components/Skeletons";
import type {
  WebhookDelivery,
  WebhookSubscription,
  WebhookWithSecret,
} from "@/lib/types";


interface Props {
  projectId: string;
}

const KNOWN_EVENTS = [
  "task.created",
  "task.moved",
  "task.assigned",
  "task.completed",
  "meeting.uploaded",
  "meeting.processed",
  "member.joined",
  "digest.sent",
];


export function WebhooksPanel({ projectId }: Props) {
  const { t } = useI18n();
  const [subs, setSubs] = useState<WebhookSubscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [secretShown, setSecretShown] = useState<{ id: string; secret: string } | null>(null);
  const [deliveriesFor, setDeliveriesFor] = useState<string | null>(null);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);

  const targetLabels: Record<string, string> = {
    generic: t("webhooks.addDialog.targetGeneric"),
    slack: "Slack",
    discord: "Discord",
  };

  const targetHints: Record<string, string> = {
    generic: "POST a JSON body. HMAC SHA-256 in X-SmartPM-Signature header.",
    slack: "Incoming webhook — paste the URL Slack gave you.",
    discord: "Discord channel webhook — paste the URL from channel settings.",
  };

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<WebhookSubscription[]>(
        `/projects/${projectId}/webhook-subscriptions`
      );
      // Defensive: backend must return an array.  If for any reason it
      // returns an object (e.g. a 200 with an error envelope), coerce
      // to an empty array so the UI doesn't crash on `.map`.
      const data = Array.isArray(res.data) ? res.data : [];
      setSubs(data);
    } catch (err: any) {
      setSubs([]);
      setError(err?.response?.data?.detail || "Failed to load webhooks");
      toast.error(err?.response?.data?.detail || "Failed to load webhooks");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [projectId]);

  async function loadDeliveries(id: string) {
    try {
      const res = await api.get<WebhookDelivery[]>(
        `/projects/${projectId}/webhook-subscriptions/${id}/deliveries?limit=50`
      );
      const data = Array.isArray(res.data) ? res.data : [];
      setDeliveries(data);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to load deliveries");
      setDeliveries([]);
    }
  }

  useEffect(() => {
    if (deliveriesFor) void loadDeliveries(deliveriesFor);
  }, [deliveriesFor]);

  async function onCreate(p: {
    target: string;
    url: string;
    events: string[];
  }) {
    try {
      const res = await api.post<WebhookWithSecret>(
        `/projects/${projectId}/webhook-subscriptions`,
        p
      );
      setSecretShown({ id: res.data.id, secret: res.data.secret });
      setShowForm(false);
      toast.success(t("webhooks.secretSaved"));
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("webhooks.createError"));
    }
  }

  async function onDelete(id: string, url: string) {
    if (!confirm(t("webhooks.deleteConfirm", url))) return;
    try {
      await api.delete(`/projects/${projectId}/webhook-subscriptions/${id}`);
      toast.success(t("webhooks.deleted"));
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("webhooks.deleteError"));
    }
  }

  async function onRotate(id: string) {
    if (!confirm("Rotate the signing secret? You'll need to update your receiver.")) return;
    try {
      const res = await api.post<WebhookWithSecret>(
        `/projects/${projectId}/webhook-subscriptions/${id}/rotate`
      );
      setSecretShown({ id: res.data.id, secret: res.data.secret });
      toast.success(t("webhooks.rotatedToast", res.data.secret));
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("webhooks.rotateError"));
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold dark:text-slate-100">{t("webhooks.title")}</h2>
        <p className="text-xs text-muted mt-1">{t("webhooks.subtitle")}</p>
      </div>
      <div className="flex justify-end">
        <button
          className="btn-primary text-sm"
          onClick={() => setShowForm((v) => !v)}
        >
          {showForm ? t("webhooks.addDialog.cancel") : t("webhooks.add")}
        </button>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {secretShown && (
        <div className="rounded-md border border-amber-400 bg-amber-50 dark:bg-amber-900/20 p-3 text-sm">
          <p className="font-semibold mb-1">{t("webhooks.secretShown", "")}</p>
          <div className="flex items-center gap-2 font-mono break-all">
            <code className="bg-white dark:bg-slate-800 px-2 py-1 rounded">
              {secretShown.secret}
            </code>
            <button
              className="text-xs text-blue-600"
              onClick={() => navigator.clipboard.writeText(secretShown.secret)}
            >
              Copy
            </button>
          </div>
          <button
            className="text-xs text-muted mt-1"
            onClick={() => setSecretShown(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {showForm && (
        <NewWebhookForm
          onSubmit={onCreate}
          onCancel={() => setShowForm(false)}
          tAdd={t}
        />
      )}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : subs.length === 0 ? (
        <div className="card text-center text-muted py-8 border-2 border-dashed border-subtle">
          {t("webhooks.noWebhooks")}
        </div>
      ) : (
        <ul className="divide-y divide-subtle">
          {subs.map((s) => (
            <li key={s.id} className="py-3">
              <div className="flex items-center gap-3 flex-wrap">
                <span
                  className={`px-2 py-0.5 rounded text-xs ${
                    s.is_active
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-200 text-gray-600"
                  }`}
                >
                  {s.is_active ? "active" : "disabled"}
                </span>
                <span className="font-mono text-xs text-muted">
                  {targetLabels[s.target]}
                </span>
                <code className="text-xs truncate max-w-md">{s.url}</code>
                <span className="text-xs text-faint">
                  {(s.events?.length ?? KNOWN_EVENTS.length)} event(s)
                </span>
                <div className="ml-auto flex gap-1 text-xs">
                  <button
                    className="text-blue-600"
                    onClick={() =>
                      setDeliveriesFor(deliveriesFor === s.id ? null : s.id)
                    }
                  >
                    {deliveriesFor === s.id ? "Hide" : t("webhooks.deliveries")}
                  </button>
                  <button className="text-amber-600" onClick={() => onRotate(s.id)}>
                    {t("webhooks.rotate")}
                  </button>
                  <button
                    className="text-red-600"
                    onClick={() => onDelete(s.id, s.url)}
                  >
                    {t("webhooks.delete")}
                  </button>
                </div>
              </div>
              {deliveriesFor === s.id && (
                <DeliveriesList deliveries={deliveries} tNoDeliveries={t("webhooks.noDeliveries")} />
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function NewWebhookForm({
  onSubmit,
  onCancel,
  tAdd,
}: {
  onSubmit: (p: { target: string; url: string; events: string[] }) => void;
  onCancel: () => void;
  tAdd: (path: string, ...args: any[]) => string;
}) {
  const [target, setTarget] = useState<"generic" | "slack" | "discord">("slack");
  const [url, setUrl] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const targetHints: Record<string, string> = {
    generic: "POST a JSON body. HMAC SHA-256 in X-SmartPM-Signature header.",
    slack: "Incoming webhook — paste the URL Slack gave you.",
    discord: "Discord channel webhook — paste the URL from channel settings.",
  };

  function toggle(ev: string) {
    const next = new Set(selected);
    if (next.has(ev)) next.delete(ev);
    else next.add(ev);
    setSelected(next);
  }

  return (
    <div className="border border-subtle rounded-md p-3 space-y-3">
      <div>
        <label className="text-xs text-muted">{tAdd("webhooks.addDialog.targetLabel")}</label>
        <select
          value={target}
          onChange={(e) => setTarget(e.target.value as any)}
          className="w-full text-sm border border-subtle rounded-md bg-white dark:bg-slate-900 dark:text-slate-100 py-1.5 mt-1"
        >
          <option value="slack">Slack</option>
          <option value="discord">Discord</option>
          <option value="generic">{tAdd("webhooks.addDialog.targetGeneric")}</option>
        </select>
        <p className="text-xs text-faint mt-1">{targetHints[target]}</p>
      </div>
      <div>
        <label className="text-xs text-muted">{tAdd("webhooks.addDialog.urlLabel")}</label>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={tAdd("webhooks.addDialog.urlPlaceholder")}
          className="w-full text-sm border border-subtle rounded-md bg-white dark:bg-slate-900 dark:text-slate-100 py-1.5 mt-1"
        />
      </div>
      <div>
        <label className="text-xs text-muted">{tAdd("webhooks.addDialog.eventsLabel")}</label>
        <div className="grid grid-cols-2 gap-1 mt-1">
          {KNOWN_EVENTS.map((ev) => (
            <label key={ev} className="text-xs flex items-center gap-1">
              <input
                type="checkbox"
                checked={selected.has(ev)}
                onChange={() => toggle(ev)}
              />
              <code>{ev}</code>
            </label>
          ))}
        </div>
      </div>
      <div className="flex gap-2">
        <button
          className="btn-primary text-sm"
          disabled={!url}
          onClick={() =>
            onSubmit({ target, url, events: Array.from(selected) })
          }
        >
          {tAdd("webhooks.addDialog.save")}
        </button>
        <button className="btn-secondary text-sm" onClick={onCancel}>
          {tAdd("webhooks.addDialog.cancel")}
        </button>
      </div>
    </div>
  );
}

function DeliveriesList({ deliveries, tNoDeliveries }: { deliveries: WebhookDelivery[]; tNoDeliveries: string }) {
  if (deliveries.length === 0) {
    return <p className="text-xs text-muted mt-2">{tNoDeliveries}</p>;
  }
  return (
    <table className="w-full text-xs mt-2">
      <thead>
        <tr className="text-left text-faint">
          <th className="py-1">Status</th>
          <th>Event</th>
          <th>HTTP</th>
          <th>Attempts</th>
          <th>When</th>
        </tr>
      </thead>
      <tbody>
        {deliveries.map((d) => (
          <tr key={d.id} className="border-t border-subtle">
            <td className="py-1">
              <span
                className={`px-1.5 py-0.5 rounded ${
                  d.status === "delivered"
                    ? "bg-green-100 text-green-700"
                    : d.status === "dead"
                    ? "bg-red-100 text-red-700"
                    : d.status === "failed"
                    ? "bg-orange-100 text-orange-700"
                    : "bg-yellow-100 text-yellow-700"
                }`}
              >
                {d.status}
              </span>
            </td>
            <td><code>{d.event}</code></td>
            <td>{d.last_status_code ?? "—"}</td>
            <td>{d.attempts}</td>
            <td className="text-faint">{new Date(d.created_at).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
