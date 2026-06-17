"use client";

import { useEffect, useRef, useState } from "react";

import { getAccessToken } from "@/lib/api";

interface UseUserWebSocketResult {
  connected: boolean;
  lastEvent: any | null;
}

const WS_RECONNECT_DELAY = 2000;

/**
 * Per-user WebSocket.  Listens for `notification` events pushed from
 * the backend (via the notification service).  Returns the most recent
 * event so the bell UI can show a toast / refresh.
 */
export function useUserWebSocket(): UseUserWebSocketResult {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<any | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    let cancelled = false;

    function connect() {
      if (cancelled) return;
      const token = getAccessToken();
      if (!token) {
        // No auth yet, try again shortly
        reconnectRef.current = window.setTimeout(connect, WS_RECONNECT_DELAY);
        return;
      }
      const explicit = (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_WS_URL) || "";
      let host: string;
      let protocol: "ws" | "wss";
      if (explicit) {
        const u = new URL(explicit);
        host = u.host;
        protocol = u.protocol === "wss:" ? "wss" : "ws";
      } else {
        // Default: hit the FastAPI backend directly on the same host as
        // the API (port 8000 in dev).  Next.js dev server does not
        // proxy WebSocket connections.
        const apiBase = (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL) || "http://localhost:8000";
        const u = new URL(apiBase);
        host = u.host;
        protocol = u.protocol === "https:" ? "wss" : "ws";
      }
      const url = `${protocol}://${host}/ws/me?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          reconnectRef.current = window.setTimeout(connect, WS_RECONNECT_DELAY);
        }
      };
      ws.onerror = () => {
        ws.close();
      };
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          setLastEvent(data);
        } catch {
          // ignore
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (reconnectRef.current) window.clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, []);

  return { connected, lastEvent };
}
