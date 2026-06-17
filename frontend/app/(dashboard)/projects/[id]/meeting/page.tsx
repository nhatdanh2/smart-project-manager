"use client";

import { useParams } from "next/navigation";
import { ChangeEvent, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { uploadToS3 } from "@/lib/s3-upload";
import { FilePreviewModal } from "@/components/FilePreviewModal";
import type { ExtractedTask, Meeting } from "@/lib/types";
import { useI18n } from "@/components/I18nProvider";
import { ListSkeleton } from "@/components/Skeletons";
import { formatDate } from "@/lib/utils";

export default function MeetingPage() {
  const params = useParams<{ id: string }>();
  const { t } = useI18n();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [meetingsLoading, setMeetingsLoading] = useState(true);
  const [selected, setSelected] = useState<Meeting | null>(null);
  const [extracted, setExtracted] = useState<ExtractedTask[]>([]);
  const [extractedLoading, setExtractedLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState<Meeting | null>(null);

  // Refs to keep the polling interval in sync with the latest meeting
  // selection without capturing stale state in the closure.
  const selectedIdRef = useRef<string | null>(null);
  const extractedRef = useRef<ExtractedTask[]>([]);
  useEffect(() => {
    selectedIdRef.current = selected?.id ?? null;
  }, [selected]);
  useEffect(() => {
    extractedRef.current = extracted;
  }, [extracted]);

  async function loadMeetings() {
    if (!params?.id) return;
    setMeetingsLoading(true);
    try {
      const res = await api.get<Meeting[]>(`/projects/${params.id}/meetings`);
      setMeetings(res.data);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to load meetings");
      setMeetings([]);
    } finally {
      setMeetingsLoading(false);
    }
  }

  async function loadExtracted(meetingId: string) {
    setExtractedLoading(true);
    try {
      const res = await api.get<ExtractedTask[]>(`/meetings/${meetingId}/extracted`);
      setExtracted(res.data);
      return res.data;
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to load extracted tasks");
      setExtracted([]);
      return [];
    } finally {
      setExtractedLoading(false);
    }
  }

  useEffect(() => {
    loadMeetings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params?.id]);

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !params?.id) return;
    setUploading(true);
    setUploadProgress(0);
    setError(null);
    try {
      try {
        const { key } = await uploadToS3({
          projectId: params.id,
          file,
          onProgress: (p) => setUploadProgress(p.percent),
        });
        const res = await api.post<Meeting>(
          `/projects/${params.id}/meetings`,
          { s3_key: key, title: file.name, file_type: file.type }
        );
        await loadMeetings();
        selectMeeting(res.data);
      } catch (s3Err: any) {
        const form = new FormData();
        form.append("file", file);
        form.append("title", file.name);
        const res = await api.post<Meeting>(
          `/projects/${params.id}/meetings`,
          form,
          { headers: { "Content-Type": "multipart/form-data" } }
        );
        await loadMeetings();
        selectMeeting(res.data);
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || t("meeting.uploadError");
      setError(msg);
      toast.error(msg);
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  }

  async function selectMeeting(m: Meeting) {
    setSelected(m);
    await loadExtracted(m.id);
  }

  async function triggerExtract() {
    if (!selected) return;
    setExtracting(true);
    setError(null);
    const meetingId = selected.id;
    const t1 = toast.loading(t("meeting.extracting2"));
    try {
      await api.post(`/meetings/${meetingId}/extract`);
      // Poll a few times then reload.  We use refs to read the latest
      // state of `extracted` and `selectedId` so the interval callback
      // doesn't close over stale values.
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts += 1;
        if (selectedIdRef.current !== meetingId) {
          // user switched meetings — stop polling
          clearInterval(poll);
          return;
        }
        const latest = await loadExtracted(meetingId);
        if (latest.length > 0 || attempts > 6) {
          clearInterval(poll);
          toast.dismiss(t1);
          toast.success(
            extractedRef.current.length > 0
              ? t("meeting.extractSuccess", extractedRef.current.length)
              : t("meeting.extractNoneFound")
          );
          await loadMeetings();
          setExtracting(false);
        }
      }, 3000);
      // Stop polling after 30s regardless
      setTimeout(() => {
        clearInterval(poll);
        setExtracting(false);
      }, 30_000);
    } catch (err: any) {
      toast.dismiss(t1);
      const msg = err?.response?.data?.detail || t("meeting.extractError");
      setError(msg);
      toast.error(msg);
      setExtracting(false);
    }
  }

  async function approve(extractedId: string) {
    if (!selected) return;
    try {
      await api.post(`/extracted-tasks/${extractedId}/approve`);
      toast.success(t("meeting.importedToast"));
      await loadExtracted(selected.id);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("meeting.importError"));
    }
  }

  async function reject(extractedId: string) {
    if (!selected) return;
    try {
      await api.post(`/extracted-tasks/${extractedId}/reject`);
      toast.success(t("meeting.skipSuccess"));
      await loadExtracted(selected.id);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("meeting.skipError"));
    }
  }

  return (
    <div className="space-y-6">
      <div className="card">
        <h2 className="font-semibold mb-3 dark:text-slate-100">{t("meeting.uploadTitle")}</h2>
        <p className="text-sm text-muted mb-3">{t("meeting.uploadHelp")}</p>
        <input
          type="file"
          accept=".txt,.md,.pdf,.mp3,.wav,.mp4,.m4a"
          onChange={onFile}
          disabled={uploading}
          className="block w-full text-sm text-body dark:text-slate-200 file:mr-3 file:py-2 file:px-4 file:rounded-md file:border-0 file:bg-primary file:text-white file:cursor-pointer"
        />
        {uploading && (
          <div className="text-sm text-muted mt-2">
            {t("meeting.uploading", uploadProgress)}
            {uploadProgress > 0 && (
              <div className="w-full bg-gray-200 dark:bg-slate-700 rounded h-1.5 mt-1">
                <div
                  className="bg-primary h-1.5 rounded transition-all"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            )}
          </div>
        )}
        {error && <div className="text-sm text-red-600 mt-2">{error}</div>}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-1 card">
          <h3 className="font-semibold mb-3 dark:text-slate-100">{t("meeting.listTitle")}</h3>
          {meetingsLoading ? (
            <ListSkeleton rows={4} />
          ) : meetings.length === 0 ? (
            <div className="text-sm text-muted text-center py-6 border-2 border-dashed border-subtle rounded">
              {t("meeting.noMeetings")}
            </div>
          ) : (
            <ul className="space-y-2">
              {meetings.map((m) => (
                <li key={m.id}>
                  <button
                    onClick={() => selectMeeting(m)}
                    className={`w-full text-left p-2 rounded border ${
                      selected?.id === m.id
                        ? "border-primary bg-indigo-50 dark:bg-indigo-900/30"
                        : "border-subtle hover:bg-gray-50 dark:hover:bg-slate-800"
                    }`}
                  >
                    <div className="font-medium text-sm dark:text-slate-100">{m.title}</div>
                    <div className="text-xs text-muted flex items-center gap-2 mt-1">
                      <span>{formatDate(m.created_at, "dd/MM/yyyy HH:mm")}</span>
                      <span
                        className={
                          m.status === "done"
                            ? "badge-success"
                            : m.status === "processing"
                            ? "badge-warning"
                            : m.status === "failed"
                            ? "badge-critical"
                            : "badge-ghost"
                        }
                      >
                        {t(
                          `meeting.meetingStatus.${m.status}` as any,
                          m.status
                        )}
                      </span>
                      {m.file_url && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setPreviewing(m);
                          }}
                          className="ml-auto text-xs text-primary hover:underline"
                        >
                          {t("meeting.preview")}
                        </button>
                      )}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="md:col-span-2 card">
          {!selected ? (
            <div className="text-sm text-muted">{t("meeting.selectPrompt")}</div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                <h3 className="font-semibold dark:text-slate-100">{selected.title}</h3>
                <button
                  onClick={triggerExtract}
                  disabled={extracting || !selected.transcript}
                  className="btn-primary"
                >
                  {extracting ? t("meeting.extracting") : t("meeting.triggerExtract")}
                </button>
              </div>
              {!selected.transcript && (
                <div className="text-sm text-yellow-700 dark:text-yellow-300 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800 rounded p-2 mb-3">
                  {t("meeting.audioNotice")}
                </div>
              )}
              {selected.transcript && (
                <details className="mb-3">
                  <summary className="cursor-pointer text-sm font-medium text-body">
                    {t("meeting.transcriptLabel", selected.transcript.length)}
                  </summary>
                  <pre className="mt-2 text-xs bg-gray-50 dark:bg-slate-800 p-3 rounded border border-subtle whitespace-pre-wrap max-h-60 overflow-y-auto text-body">
                    {selected.transcript}
                  </pre>
                </details>
              )}
              <h4 className="font-semibold text-sm mb-2 dark:text-slate-100">
                {t("meeting.extractedHeader", extracted.length)}
              </h4>
              {extractedLoading && extracted.length === 0 ? (
                <ListSkeleton rows={3} />
              ) : extracted.length === 0 ? (
                <div className="text-sm text-muted">{t("meeting.extractedEmpty")}</div>
              ) : (
                <ul className="space-y-2">
                  {extracted.map((e) => {
                    const data = e.task_data as Record<string, any>;
                    return (
                      <li
                        key={e.id}
                        className="p-3 border border-subtle rounded-md flex items-start gap-3"
                      >
                        <div className="flex-1">
                          <div className="font-medium text-sm dark:text-slate-100">
                            {data.title || t("meeting.noTitle")}
                          </div>
                          <div className="text-xs text-muted mt-1">
                            {t("meeting.extractedMeta",
                              data.assignee_name || t("meeting.assigneeEmpty"),
                              data.story_points || 1,
                              data.deadline_text || t("meeting.deadlineEmpty")
                            )}
                          </div>
                          {data.description && (
                            <div className="text-xs text-body mt-1 line-clamp-2">
                              {data.description}
                            </div>
                          )}
                        </div>
                        {e.is_approved ? (
                          <span className="badge-success">{t("meeting.imported")}</span>
                        ) : (
                          <div className="flex gap-1">
                            <button
                              onClick={() => approve(e.id)}
                              className="btn-primary text-xs px-2 py-1"
                              aria-label="Approve"
                            >
                              ✓
                            </button>
                            <button
                              onClick={() => reject(e.id)}
                              className="btn-secondary text-xs px-2 py-1"
                              aria-label="Reject"
                            >
                              ✗
                            </button>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </>
          )}
        </div>
      </div>

      <FilePreviewModal
        meetingId={previewing?.id ?? null}
        filename={previewing?.title}
        open={!!previewing}
        onOpenChange={(o) => !o && setPreviewing(null)}
      />
    </div>
  );
}
