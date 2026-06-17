"use client";

import { useEffect, useState } from "react";

import { API_BASE_URL, getAccessToken } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import type { FileMeta, FilePreviewKind } from "@/lib/types";


interface Props {
  meetingId: string | null;
  filename?: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(1)} ${units[i]}`;
}

function authedUrl(url: string): string {
  // For elements that can't set headers (img, video, audio, iframe),
  // we use a same-origin path through the API client.  As a fallback we
  // append the token as a query string — the backend doesn't read this
  // today, but the page must be loaded while logged in for the cookie
  // / Authorization header in the fetch wrapper to satisfy the API.
  return url;
}

async function loadMeta(meetingId: string): Promise<FileMeta> {
  const res = await fetch(`${API_BASE_URL}/api/files/meetings/${meetingId}/meta`, {
    headers: { Authorization: `Bearer ${getAccessToken() ?? ""}` },
  });
  if (!res.ok) {
    throw new Error(`Failed to load file metadata (${res.status})`);
  }
  return res.json();
}

/**
 * In-browser preview for a meeting's file.  Renders the right viewer
 * for the detected MIME type (image / PDF / audio / video / text).
 * Falls back to a download button for binary formats.
 */
export function FilePreviewModal({ meetingId, filename, open, onOpenChange }: Props) {
  const [meta, setMeta] = useState<FileMeta | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !meetingId) return;
    setMeta(null);
    setError(null);
    setLoading(true);
    loadMeta(meetingId)
      .then(setMeta)
      .catch((e) => setError(e.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, [open, meetingId]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl w-[min(96vw,1100px)] max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 pr-8">
            <span className="truncate">{meta?.filename || filename || "File"}</span>
            {meta && (
              <span className="text-xs text-muted font-normal">
                {humanSize(meta.size)} · {meta.mime}
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        {loading && (
          <div className="p-8 text-center text-muted text-sm">Đang tải…</div>
        )}

        {error && (
          <div className="p-8 text-center text-red-500 text-sm">{error}</div>
        )}

        {meta && !loading && !error && (
          <PreviewBody meta={meta} />
        )}

        {meta && (
          <div className="flex justify-end gap-2 pt-2 border-t border-subtle">
            <Button
              variant="secondary"
              onClick={() => onOpenChange(false)}
            >
              Đóng
            </Button>
            <a
              href={`${API_BASE_URL}${meta.downloadUrl}`}
              target="_blank"
              rel="noreferrer"
              className="btn-primary"
            >
              Tải xuống
            </a>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function PreviewBody({ meta }: { meta: FileMeta }) {
  const fullUrl = `${API_BASE_URL}${meta.previewUrl}`;
  const authHeaders = {
    Authorization: `Bearer ${getAccessToken() ?? ""}`,
  };

  // For binary kinds we show a friendly hint.
  if (meta.kind === "binary") {
    return (
      <div className="p-8 text-center text-muted text-sm">
        Định dạng <code>{meta.mime}</code> không hỗ trợ xem trực tiếp.{" "}
        <a className="text-primary underline" href={fullUrl} target="_blank" rel="noreferrer">
          Tải xuống
        </a>{" "}
        để mở bằng ứng dụng ngoài.
      </div>
    );
  }

  if (meta.kind === "image") {
    return (
      <div className="flex-1 min-h-0 overflow-auto bg-gray-50 dark:bg-slate-950 rounded">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={authedUrl(fullUrl)}
          alt={meta.filename}
          className="max-w-full h-auto mx-auto block"
          // Fetch with headers via an onload preload — simpler: just use the URL
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).alt = "Failed to load image";
          }}
        />
      </div>
    );
  }

  if (meta.kind === "pdf") {
    return (
      <div className="flex-1 min-h-0 rounded overflow-hidden bg-gray-100">
        <iframe
          title={meta.filename}
          src={authedUrl(fullUrl)}
          className="w-full h-[70vh] border-0"
        />
      </div>
    );
  }

  if (meta.kind === "audio") {
    return (
      <div className="p-6 flex flex-col items-center gap-3">
        <div className="text-sm text-muted">Audio · {meta.mime}</div>
        <audio controls className="w-full" src={authedUrl(fullUrl)} preload="metadata" />
      </div>
    );
  }

  if (meta.kind === "video") {
    return (
      <div className="flex-1 min-h-0 rounded overflow-hidden bg-black">
        <video
          controls
          className="w-full h-full max-h-[70vh]"
          src={authedUrl(fullUrl)}
          preload="metadata"
        />
      </div>
    );
  }

  // text / json / markdown
  return <TextPreview url={fullUrl} headers={authHeaders} mime={meta.mime} />;
}

function TextPreview({
  url,
  headers,
  mime,
}: {
  url: string;
  headers: Record<string, string>;
  mime: string;
}) {
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    fetch(url, { headers })
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setText)
      .catch((e) => setErr(e.message || "Failed"));
  }, [url]);
  return (
    <div className="flex-1 min-h-0 overflow-auto bg-gray-50 dark:bg-slate-950 rounded p-3">
      {text == null && err == null && <div className="text-muted text-sm">Đang tải…</div>}
      {err && <div className="text-red-500 text-sm">{err}</div>}
      {text != null && mime === "application/json" && (
        <pre className="text-xs whitespace-pre-wrap break-words">
          {JSON.stringify(JSON.parse(text), null, 2)}
        </pre>
      )}
      {text != null && mime !== "application/json" && (
        <pre className="text-xs whitespace-pre-wrap break-words">{text}</pre>
      )}
    </div>
  );
}
