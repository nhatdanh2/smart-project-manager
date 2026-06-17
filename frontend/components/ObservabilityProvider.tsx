"use client";

import { useEffect } from "react";

import { initSentry } from "@/lib/observability";

/**
 * Mounts Sentry on the client.  No-op when NEXT_PUBLIC_SENTRY_DSN
 * is not set.
 */
export function ObservabilityProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    initSentry();
  }, []);
  return <>{children}</>;
}
