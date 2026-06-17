"use client";

import { useEffect } from "react";

import { captureException } from "@/lib/observability";

/**
 * Next.js global-error boundary.  Catches errors thrown in the root
 * layout itself (which the normal error.tsx cannot catch) and
 * forwards them to Sentry.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    captureException(error, { digest: error.digest });
  }, [error]);

  return (
    <html>
      <body
        style={{
          fontFamily: "system-ui, -apple-system, sans-serif",
          padding: "2rem",
          textAlign: "center",
          color: "#1f2937",
        }}
      >
        <h1 style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>
          Đã xảy ra lỗi nghiêm trọng
        </h1>
        <p style={{ color: "#6b7280", marginBottom: "1.5rem" }}>
          Vui lòng thử lại. Nếu vẫn lỗi, hãy liên hệ support.
        </p>
        <button
          onClick={() => reset()}
          style={{
            background: "#4f46e5",
            color: "white",
            padding: "0.5rem 1rem",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
          }}
        >
          Tải lại
        </button>
      </body>
    </html>
  );
}
