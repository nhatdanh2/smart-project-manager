"""AI extraction job (formerly in-process during upload).

Pulls a meeting out of ``pending`` state, transcribes audio (if
needed) and asks the LLM for structured task extractions, then
saves them to ``extracted_tasks`` and notifies the project.
"""
from __future__ import annotations

import logging

from app.database import SessionLocal
from app.models.meeting import ExtractedTask, Meeting
from app.services.realtime import broadcast_sync
from app.services.search_service import delete_meeting, index_meeting


logger = logging.getLogger(__name__)


def extract_meeting_actions(meeting_id: str) -> dict:
    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            return {"status": "not_found"}
        if meeting.status not in ("pending", "processing"):
            return {"status": "skipped", "current": meeting.status}
        meeting.status = "processing"
        db.add(meeting)
        db.commit()

        # ---- transcription ------------------------------------------------
        transcript = meeting.transcript or ""
        if not transcript and meeting.file_type == "audio":
            try:
                from app.services.transcription_service import transcribe_audio
                from app.config import settings
                from pathlib import Path

                full_path = settings.UPLOAD_DIR.parent / meeting.file_url
                if full_path.exists():
                    transcript = transcribe_audio(full_path)
                    meeting.transcript = transcript
                    db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("transcription failed: %s", exc)

        # ---- AI extraction -----------------------------------------------
        if transcript:
            try:
                from app.services.ai_secretary import extract_tasks_from_meeting

                # Build member list
                from app.models.project import ProjectMember as PM
                from app.models.user import User as U
                member_names = [
                    r[0]
                    for r in db.query(U.name)
                    .join(PM, PM.user_id == U.id)
                    .filter(PM.project_id == meeting.project_id)
                    .all()
                ]
                extracted = await extract_tasks_from_meeting(
                    content=transcript,
                    project_members=member_names,
                )
                for item in extracted:
                    db.add(
                        ExtractedTask(
                            meeting_id=meeting.id,
                            task_data=item,
                            is_approved=False,
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("AI extraction failed: %s", exc)

        meeting.status = "done"
        db.commit()
        index_meeting(
            {
                "id": meeting.id,
                "project_id": meeting.project_id,
                "title": meeting.title or "",
                "transcript": (meeting.transcript or "")[:10_000],
                "status": meeting.status,
                "created_at": int(meeting.created_at.timestamp()) if meeting.created_at else 0,
            }
        )
        broadcast_sync(
            meeting.project_id,
            {"type": "meeting.processed", "meetingId": meeting.id},
        )
        return {"status": "done", "meetingId": meeting.id}
    except Exception as exc:  # noqa: BLE001
        logger.exception("extract_meeting_actions failed: %s", exc)
        try:
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            if meeting:
                meeting.status = "failed"
                db.commit()
        except Exception:
            pass
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()
