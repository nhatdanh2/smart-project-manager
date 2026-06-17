"use client";

import { useEffect, useRef, useState } from "react";

import { getAccessToken, API_BASE_URL } from "@/lib/api";

export interface PresenceMember {
  userId: string;
  name: string;
  lastSeen: number;
}

interface UseProjectPresenceResult {
  members: PresenceMember[];
  connected: boolean;
}

const WS_RETRY_BASE_MS = 1500;
const WS_RETRY_MAX_MS = 15000;

/**
 * Live presence for a project.  Subscribes to /ws/projects/{id} and
 * exposes the latest ``presence`` event the server broadcasts.
 */
export function useProjectPresence(projectId: string | null): UseProjectPresenceResult {
  const [members, setMembers] = useState<PresenceMember[]>([]);
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
      const wsUrl = (
        process.env.NEXT_PUBLIC_WS_URL || API_BASE_URL.replace(/^http/, "ws")
      ).replace(/\/$/, "");
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
        const delay = Math.min(WS_RETRY_MAX_MS, WS_RETRY_BASE_MS * 2 ** retryRef.current);
        retryRef.current += 1;
        setTimeout(connect, delay);
      };
      ws.onerror = () => {
        ws.close();
      };
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === "presence" && Array.isArray(data.members)) {
            setMembers(data.members as PresenceMember[]);
          }
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

  return { members, connected };
}
