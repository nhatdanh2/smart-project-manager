"""File serving / preview endpoints.

Streams the bytes stored under ``settings.UPLOAD_DIR`` with the right
``Content-Type``, supports HTTP ``Range`` for media, and requires the
caller to be a project member.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.meeting import Meeting
from app.models.project import ProjectMember
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.file_service import detect_mime, parse_range_header, resolve_uploaded_file


router = APIRouter(prefix=f"{settings.API_PREFIX}/files", tags=["files"])


def _ensure_project_member(db: Session, project_id: str, user_id: str) -> None:
    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a project member")


@router.get("/meetings/{meeting_id}/preview")
def preview_meeting_file(
    meeting_id: str,
    request: Request,
    download: bool = Query(False, description="Force download with Content-Disposition"),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Stream the meeting's file for in-browser preview.

    Returns the right ``Content-Type`` for PDF / image / audio / video
    and honours HTTP ``Range`` so that large media can be scrubbed.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    _ensure_project_member(db, meeting.project_id, current.id)

    path = resolve_uploaded_file(meeting.file_url)
    mime = detect_mime(path)
    file_size = path.stat().st_size
    range_header = request.headers.get("range")
    rng = parse_range_header(range_header, file_size)

    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=300",
        "Content-Length": str(file_size),
        "X-Content-Type-Options": "nosniff",
    }
    if download:
        filename = path.name
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    else:
        headers["Content-Disposition"] = f'inline; filename="{path.name}"'

    if rng is None:
        # Full content
        return FileResponse(
            path,
            media_type=mime,
            headers=headers,
        )

    start, end = rng
    chunk_size = end - start + 1
    headers["Content-Length"] = str(chunk_size)
    headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

    def _iter():
        with path.open("rb") as f:
            f.seek(start)
            remaining = chunk_size
            buf = 64 * 1024
            while remaining > 0:
                data = f.read(min(buf, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    return Response(
        content=_iter(),
        status_code=206,
        media_type=mime,
        headers=headers,
    )


@router.get("/meetings/{meeting_id}/meta")
def get_meeting_file_meta(
    meeting_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Small JSON describing the file (size, mime, …).

    Used by the frontend to choose the right viewer without first
    streaming the bytes.  When S3 is enabled the response includes
    a presigned download URL that the browser can hit directly
    (no bytes flow through the API).
    """
    from app.services import s3_service

    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    _ensure_project_member(db, meeting.project_id, current.id)

    mime: str
    size: int
    filename: str

    if s3_service.is_enabled() and meeting.file_url:
        # When using S3, file_url is the S3 object key.
        filename = meeting.file_url.rsplit("/", 1)[-1]
        try:
            head = s3_service._client().head_object(
                Bucket=settings.S3_BUCKET_NAME, Key=meeting.file_url
            )
            size = int(head.get("ContentLength", 0))
            mime = head.get("ContentType", "application/octet-stream")
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=404, detail="Object not found in S3") from exc
        download_url = s3_service.generate_download_url(
            meeting.file_url, response_content_type=mime
        )
        # Presigned URLs include the signature in the query string;
        # the meta response itself is small and cached briefly.
        return {
            "meetingId": meeting_id,
            "filename": filename,
            "size": size,
            "mime": mime,
            "kind": _kind_from_mime(mime),
            "previewUrl": download_url,   # browser will GET this directly
            "downloadUrl": download_url,
            "backend": "s3",
        }

    # Local-FS fallback
    path = resolve_uploaded_file(meeting.file_url)
    mime = detect_mime(path)
    size = path.stat().st_size
    return {
        "meetingId": meeting_id,
        "filename": path.name,
        "size": size,
        "mime": mime,
        "kind": _kind_from_mime(mime),
        "previewUrl": f"/api/files/meetings/{meeting_id}/preview",
        "downloadUrl": f"/api/files/meetings/{meeting_id}/preview?download=true",
        "backend": "local",
    }


def _kind_from_mime(mime: str) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime == "application/pdf":
        return "pdf"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("text/") or mime in ("application/json", "application/xml"):
        return "text"
    return "binary"


@router.post("/presign-upload")
def presign_upload(
    project_id: str = Query(..., description="Project the file belongs to"),
    filename: str = Query(..., description="Original filename, used to derive the S3 key + content type"),
    content_type: str = Query("application/octet-stream"),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Return a presigned PUT URL the browser can use to upload directly to S3.

    The backend never sees the file bytes; the client gets back the
    URL and the S3 object key, then PUTs the file in chunks (or one
    go for small files) and tells the API the meeting id it belongs
    to.
    """
    from app.services import s3_service

    if not s3_service.is_enabled():
        raise HTTPException(
            status_code=501,
            detail="Direct upload is disabled; S3_BUCKET_NAME is not configured",
        )
    _ensure_project_member(db, project_id, current.id)
    # Build a deterministic but unique key.  We don't trust the
    # browser to give us the right filename; we sanitize + prefix.
    import re
    from uuid import uuid4

    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:120] or "file"
    key = f"projects/{project_id}/meetings/{uuid4().hex}-{safe}"
    upload_url = s3_service.generate_upload_url(key, content_type=content_type)
    return {
        "uploadUrl": upload_url,
        "key": key,
        "method": "PUT",
        "headers": {"Content-Type": content_type},
        "expiresIn": settings.S3_PRESIGN_EXPIRES_SECONDS,
    }
