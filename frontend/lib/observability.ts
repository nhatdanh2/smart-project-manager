"use client";

/**
 * Frontend observability helpers.  All exports are no-ops unless the
 * corresponding env var is set; this keeps the bundle small in dev.
 */
import { useEffect } from "react";

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;
const SENTRY_TRACES_SAMPLE_RATE = Number(
  process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE || "0.1"
);
const SENTRY_REPLAY_SAMPLE_RATE = Number(
  process.env.NEXT_PUBLIC_SENTRY_REPLAY_SAMPLE_RATE || "0.0"
);

let initialised = false;
let sentryRef: any = null;

export async function initSentry() {
  if (initialised) return;
  initialised = true;
  if (!SENTRY_DSN) {
    // eslint-disable-next-line no-console
    console.info("[observability] Sentry disabled (NEXT_PUBLIC_SENTRY_DSN not set)");
    return;
  }
  try {
    const Sentry = await import("@sentry/nextjs");
    sentryRef = Sentry;
    Sentry.init({
      dsn: SENTRY_DSN,
      tracesSampleRate: SENTRY_TRACES_SAMPLE_RATE,
      replaysOnErrorSampleRate: Math.max(SENTRY_REPLAY_SAMPLE_RATE, 0.1),
      replaysSessionSampleRate: SENTRY_REPLAY_SAMPLE_RATE,
      environment: process.env.NEXT_PUBLIC_SENTRY_ENV || "development",
      release: process.env.NEXT_PUBLIC_SENTRY_RELEASE,
      integrations: [
        Sentry.browserTracingIntegration(),
        Sentry.replayIntegration(),
      ].filter(Boolean),
    });
    // eslint-disable-next-line no-console
    console.info("[observability] Sentry initialised");
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn("[observability] Sentry not installed:", e);
  }
}

export function captureException(err: unknown, context?: Record<string, unknown>) {
  if (!sentryRef) return;
  try {
    sentryRef.captureException(err, { extra: context });
  } catch {
    // noop
  }
}

export function setUserContext(user: { id: string; name?: string; email?: string }) {
  if (!sentryRef) return;
  try {
    sentryRef.setUser(user);
  } catch {
    // noop
  }
}

export function clearUserContext() {
  if (!sentryRef) return;
  try {
    sentryRef.setUser(null);
  } catch {
    // noop
  }
}

/**
 * Convenience hook: calls initSentry() on mount.  Use once in the
 * root layout.
 */
export function useSentry() {
  useEffect(() => {
    initSentry();
  }, []);
}
