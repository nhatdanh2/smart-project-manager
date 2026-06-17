"use client";

import { useEffect, useRef, useState } from "react";

import { getAccessToken, API_BASE_URL } from "@/lib/api";

export type WSEvent = Record<string, unknown> & { type: string };

export function useProjectWebSocket(projectId: string | null) {
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);

  useEffect(() => {
    if (!projectId) return;
    const token = getAccessToken();
    if (!token) return;

    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      const wsUrl = (process.env.NEXT_PUBLIC_WS_URL || API_BASE_URL.replace(/^http/, "ws"))
        .replace(/\/$/, "");
      const url = `${wsUrl}/ws/projects/${projectId}?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        retryRef.current = 0;
      };
      ws.onclose = () => {
        setConnected(false);
        if (cancelled) return;
        // Per PRD: reconnect every 3 seconds.  Cap retries at 10
        // so we don't loop forever in dev when the server is down.
        if (retryRef.current >= 10) return;
        retryRef.current += 1;
        setTimeout(connect, 3000);
      };
      ws.onerror = () => {
        ws.close();
      };
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data) as WSEvent;
          setEvents((prev) => [...prev.slice(-49), data]);
        } catch {
          // ignore
        }
      };
    };

    connect();
    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, [projectId]);

  return { events, connected };
}
