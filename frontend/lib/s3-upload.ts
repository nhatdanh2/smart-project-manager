/**
 * Direct upload to S3 via a presigned PUT URL.
 *
 * The backend never sees the file bytes; this whole module is
 * browser-side XHR + progress.
 */

import { API_BASE_URL, getAccessToken } from "./api";
import type { PresignedUpload } from "./types";


export interface UploadProgress {
  loaded: number;
  total: number;
  percent: number;
}

export interface UploadOptions {
  projectId: string;
  file: File;
  onProgress?: (p: UploadProgress) => void;
  signal?: AbortSignal;
}

/**
 * Get a presigned PUT URL from the backend, then PUT the file
 * directly to S3.  Resolves with the S3 key once the upload is
 * done.
 */
export async function uploadToS3({
  projectId,
  file,
  onProgress,
  signal,
}: UploadOptions): Promise<{ key: string }> {
  // 1. Ask the API for a presigned URL
  const presignRes = await fetch(
    `${API_BASE_URL}/api/files/presign-upload?` +
      new URLSearchParams({
        project_id: projectId,
        filename: file.name,
        content_type: file.type || "application/octet-stream",
      }),
    {
      method: "POST",
      headers: { Authorization: `Bearer ${getAccessToken() ?? ""}` },
      signal,
    }
  );
  if (!presignRes.ok) {
    throw new Error(
      `Failed to get presigned URL: ${presignRes.status} ${await presignRes.text()}`
    );
  }
  const presigned: PresignedUpload = await presignRes.json();

  // 2. PUT the file directly to S3 using XHR so we can report progress
  await new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(presigned.method, presigned.uploadUrl, true);
    for (const [k, v] of Object.entries(presigned.headers)) {
      xhr.setRequestHeader(k, v);
    }
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      onProgress?.({
        loaded: e.loaded,
        total: e.total,
        percent: Math.round((e.loaded / e.total) * 100),
      });
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new Error(`S3 PUT failed: ${xhr.status} ${xhr.responseText}`));
    };
    xhr.onerror = () => reject(new Error("Network error during S3 upload"));
    xhr.onabort = () => reject(new Error("Upload aborted"));
    if (signal) {
      signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }
    xhr.send(file);
  });

  return { key: presigned.key };
}
