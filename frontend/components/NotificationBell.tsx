"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, Check } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";
import { useI18n } from "@/components/I18nProvider";
import { useUserWebSocket } from "@/hooks/useUserWebSocket";
import { Skeleton } from "@/components/Skeletons";
import type { Notification } from "@/lib/types";

export function NotificationBell() {
  const router = useRouter();
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unread, setUnread] = useState(0);
  const ref = useRef<HTMLDivElement | null>(null);
  const { lastEvent, connected } = useUserWebSocket();

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<Notification[]>("/notifications?limit=20");
      setItems(res.data);
      setUnread(res.data.filter((n) => !n.is_read).length);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load notifications");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.type === "notification") {
      const n: Notification = {
        id: lastEvent.id,
        user_id: "",
        project_id: lastEvent.projectId ?? null,
        type: lastEvent.notifType,
        title: lastEvent.title,
        body: lastEvent.body ?? null,
        link: lastEvent.link ?? null,
        is_read: false,
        created_at: lastEvent.createdAt ?? new Date().toISOString(),
      };
      setItems((prev) => [n, ...prev].slice(0, 50));
      setUnread((u) => u + 1);
      toast(n.title, {
        description: n.body ?? undefined,
        action: n.link
          ? {
              label: t("notification.open"),
              onClick: () => router.push(n.link!),
            }
          : undefined,
      });
    }
  }, [lastEvent, router, t]);

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [open]);

  async function markAll() {
    try {
      await api.post("/notifications/read-all", {});
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnread(0);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to mark all read");
    }
  }

  async function markRead(id: string, link?: string | null) {
    try {
      await api.post(`/notifications/${id}/read`, {});
    } catch (err: any) {
      // ignore - the UI update is optimistic
    }
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
    setUnread((u) => Math.max(0, u - 1));
    if (link) {
      setOpen(false);
      router.push(link);
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="btn-ghost p-2 rounded-md relative"
        title={t("notification.title")}
        aria-label="Notifications"
      >
        <Bell className="w-4 h-4" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-[10px] rounded-full min-w-[16px] h-4 flex items-center justify-center px-1">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
        {connected && (
          <span className="absolute bottom-0 right-0 w-2 h-2 rounded-full bg-green-500" />
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 max-w-[90vw] bg-white dark:bg-slate-900 border border-subtle rounded-lg shadow-lg z-50 overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 border-b border-subtle">
            <div className="font-semibold text-sm dark:text-slate-100">
              {t("notification.title")} {unread > 0 && <span className="badge-primary ml-1">{unread}</span>}
            </div>
            {unread > 0 && (
              <button
                onClick={markAll}
                className="text-xs text-primary hover:underline flex items-center gap-1"
              >
                <Check className="w-3 h-3" />
                {t("notification.markAll")}
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto scroll-thin">
            {loading && items.length === 0 ? (
              <div className="p-3 space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : error && items.length === 0 ? (
              <div className="p-6 text-sm text-red-500 text-center">{error}</div>
            ) : items.length === 0 ? (
              <div className="p-6 text-sm text-muted text-center">
                {t("notification.empty")}
              </div>
            ) : (
              <ul>
                {items.map((n) => (
                  <li
                    key={n.id}
                    onClick={() => markRead(n.id, n.link)}
                    className={cn(
                      "p-3 border-b border-subtle last:border-0 cursor-pointer hover:bg-gray-50 dark:hover:bg-slate-800",
                      !n.is_read && "bg-indigo-50/30 dark:bg-indigo-900/10"
                    )}
                  >
                    <div className="flex items-start gap-2">
                      {!n.is_read && (
                        <span className="mt-1.5 w-2 h-2 rounded-full bg-primary flex-shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium dark:text-slate-100">
                          {n.title}
                        </div>
                        {n.body && (
                          <div className="text-xs text-muted mt-0.5 line-clamp-2">
                            {n.body}
                          </div>
                        )}
                        <div className="text-xs text-faint mt-1">
                          {formatDate(n.created_at, "dd/MM HH:mm")}
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
