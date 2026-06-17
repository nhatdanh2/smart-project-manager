"""Meetings router: upload meeting notes, list, get detail, trigger extraction."""
from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.rate_limit import limiter
from app.models.meeting import ExtractedTask, Meeting
from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.user import User
from app.schemas.ai import ExtractedTaskOut, MeetingOut
from app.services.auth_service import get_current_user
from app.services.realtime import broadcast_sync


logger = logging.getLogger(__name__)
router = APIRouter(prefix=f"{settings.API_PREFIX}", tags=["meetings"])


TEXT_EXT = {".txt", ".md", ".markdown"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".mp4"}


def _ensure_member(db: Session, project_id: str, user_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pm = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        .first()
    )
    if not pm:
        raise HTTPException(status_code=403, detail="Not a project member")
    return project


def _save_upload(file: UploadFile, project_id: str) -> tuple[Path, str, int]:
    """Persist the uploaded file to settings.UPLOAD_DIR and return (path, ext, size)."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (TEXT_EXT | AUDIO_EXT | {".pdf"}):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
    project_dir = settings.UPLOAD_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = Path(file.filename or "upload").name
    dest = project_dir / f"{timestamp}_{safe_name}"
    size = 0
    with dest.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            max_bytes = (
                settings.MAX_UPLOAD_BYTES_AUDIO
                if ext in AUDIO_EXT
                else settings.MAX_UPLOAD_BYTES_TEXT
            )
            if size > max_bytes:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds size limit ({max_bytes} bytes)",
                )
            out.write(chunk)
    return dest, ext, size


@router.post(
    "/projects/{project_id}/meetings",
    response_model=MeetingOut,
    status_code=201,
)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_meeting(
    request: Request,
    project_id: str,
    title: Optional[str] = Form(None),
    s3_key: Optional[str] = Form(None),
    file_type: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingOut:
    """Upload a meeting file.

    Two paths:
    1.  Multipart ``file=`` (current behaviour; goes through the API)
    2.  ``s3_key=`` for the direct-upload flow — the browser PUTs the
        bytes to S3 with a presigned URL and just tells us the key.
    """
    _ensure_member(db, project_id, current.id)

    from app.services import s3_service

    if s3_key:
        # ---------- Path 1: direct S3 upload ----------
        if not s3_service.is_enabled():
            raise HTTPException(status_code=400, detail="S3 is not configured")
        try:
            head = s3_service._client().head_object(
                Bucket=settings.S3_BUCKET_NAME, Key=s3_key
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400, detail=f"S3 object not found: {s3_key}"
            ) from exc
        ext = Path(s3_key).suffix.lower()
        meeting = Meeting(
            project_id=project_id,
            title=title or Path(s3_key).name,
            file_url=s3_key,            # store the S3 key
            file_type=file_type or ("audio" if ext in AUDIO_EXT else "text"),
            status="pending",
            created_by=current.id,
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        try:
            from app.workers.tasks import process_meeting_file

            process_meeting_file.delay(meeting.id)
        except Exception:
            from app.jobs.ai_extraction_job import extract_meeting_actions

            try:
                extract_meeting_actions(meeting.id)
            except Exception:
                pass
        return meeting

    # ---------- Path 2: traditional multipart ----------
    if not file:
        raise HTTPException(
            status_code=400,
            detail="Provide either a multipart 'file' or an 's3_key' form field",
        )
    dest, ext, size = _save_upload(file, project_id)
    file_type = "audio" if ext in AUDIO_EXT else "text"
    transcript: Optional[str] = None
    if ext in TEXT_EXT:
        try:
            transcript = dest.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            transcript = None
    meeting = Meeting(
        project_id=project_id,
        title=title or file.filename,
        file_url=str(dest.relative_to(settings.UPLOAD_DIR.parent)),
        file_type=file_type,
        transcript=transcript,
        status="done" if transcript else "processing" if file_type == "audio" else "pending",
        created_by=current.id,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    broadcast_sync(project_id, {"type": "meeting.uploaded", "meetingId": meeting.id})
    # Webhook
    try:
        from app.services.webhook_service import emit_event

        emit_event(
            db,
            project_id=project_id,
            event="meeting.uploaded",
            data={
                "text": f"📄 New meeting: {meeting.title}",
                "meeting_id": meeting.id,
                "title": meeting.title,
                "uploaded_by": current.id,
            },
        )
    except Exception:
        pass
    # Notify project members
    from app.services.notification_service import notify_project_members

    notify_project_members(
        db,
        project_id=project_id,
        type="meeting.uploaded",
        title=f"📄 Biên bản mới: {meeting.title}",
        body=f"{current.name} vừa upload biên bản họp.",
        link=f"/projects/{project_id}/meeting",
        exclude_user_id=current.id,
    )

    # Auto-transcribe audio files in the request lifecycle.  This is a
    # short blocking call (Whisper typically <5s) and we don't have a
    # worker infrastructure yet for Phase 2.  In production this would
    # be enqueued to Celery (see app.workers.tasks.process_meeting_file).
    if file_type == "audio" and not transcript:
        try:
            from app.services.transcription_service import transcribe_audio

            full_path = settings.UPLOAD_DIR.parent / meeting.file_url
            if full_path.exists():
                transcript_text = await transcribe_audio(full_path)
                meeting.transcript = transcript_text
                meeting.status = "pending"  # ready for AI extraction
                db.commit()
                db.refresh(meeting)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Auto-transcription failed: %s", exc)
            meeting.status = "pending"
            db.commit()
            db.refresh(meeting)
    return MeetingOut.model_validate(meeting)


@router.get(
    "/projects/{project_id}/meetings", response_model=List[MeetingOut]
)
def list_meetings(
    project_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[MeetingOut]:
    _ensure_member(db, project_id, current.id)
    meetings = (
        db.query(Meeting)
        .filter(Meeting.project_id == project_id)
        .order_by(Meeting.created_at.desc())
        .all()
    )
    return [MeetingOut.model_validate(m) for m in meetings]


@router.get("/meetings/{meeting_id}", response_model=MeetingOut)
def get_meeting(
    meeting_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingOut:
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    _ensure_member(db, meeting.project_id, current.id)
    return MeetingOut.model_validate(meeting)


@router.post(
    "/meetings/{meeting_id}/extract",
    response_model=List[ExtractedTaskOut],
)
async def extract_meeting(
    meeting_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[ExtractedTaskOut]:
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    _ensure_member(db, meeting.project_id, current.id)

    # Get member names for AI matching
    members = (
        db.query(User)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .filter(ProjectMember.project_id == meeting.project_id)
        .all()
    )
    member_names = [m.name for m in members]
    name_to_id = {m.name.lower(): m.id for m in members}

    # If meeting has no transcript yet, try to read the text file or
    # transcribe the audio file via Whisper.
    if not meeting.transcript and meeting.file_url:
        full_path = settings.UPLOAD_DIR.parent / meeting.file_url
        if meeting.file_type == "text" and full_path.exists():
            try:
                meeting.transcript = full_path.read_text(
                    encoding="utf-8", errors="ignore"
                )
            except Exception:
                pass
        elif meeting.file_type == "audio" and full_path.exists():
            try:
                from app.services.transcription_service import transcribe_audio

                meeting.transcript = await transcribe_audio(full_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Transcription on extract failed: %s", exc)
    if not meeting.transcript:
        raise HTTPException(
            status_code=400,
            detail="Meeting has no transcript. Upload a .txt file or set OPENAI_API_KEY for audio.",
        )

    from app.services.ai_secretary import extract_tasks_from_meeting

    extracted = await extract_tasks_from_meeting(meeting.transcript, member_names)

    # Persist extracted rows (replace previous ones for the same meeting)
    db.query(ExtractedTask).filter(ExtractedTask.meeting_id == meeting_id).delete()
    rows: List[ExtractedTask] = []
    for item in extracted:
        # Annotate with resolved assignee_id (if name matches)
        annotated = dict(item)
        assignee_name = annotated.get("assignee_name")
        if assignee_name and isinstance(assignee_name, str):
            annotated["assignee_id"] = name_to_id.get(assignee_name.strip().lower())
        rows.append(
            ExtractedTask(
                meeting_id=meeting_id,
                task_data=annotated,
                is_approved=False,
            )
        )
    db.add_all(rows)
    meeting.status = "done"
    db.commit()
    for r in rows:
        db.refresh(r)
    broadcast_sync(
        meeting.project_id,
        {"type": "meeting.extracted", "meetingId": meeting_id, "count": len(rows)},
    )
    return [ExtractedTaskOut.model_validate(r) for r in rows]


@router.get(
    "/meetings/{meeting_id}/extracted", response_model=List[ExtractedTaskOut]
)
def list_extracted(
    meeting_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[ExtractedTaskOut]:
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    _ensure_member(db, meeting.project_id, current.id)
    rows = (
        db.query(ExtractedTask)
        .filter(ExtractedTask.meeting_id == meeting_id)
        .order_by(ExtractedTask.created_at.asc())
        .all()
    )
    return [ExtractedTaskOut.model_validate(r) for r in rows]
