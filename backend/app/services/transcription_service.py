"""Audio transcription service.

Uses OpenAI's Whisper API when ``OPENAI_API_KEY`` is set; otherwise falls
back to a deterministic stub that returns Vietnamese placeholder content
so the rest of the meeting pipeline stays testable in dev.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from app.config import settings


logger = logging.getLogger(__name__)


# Vietnamese demo transcript used by the stub when Whisper is unavailable.
# It is structured to look like a real student project sync so the AI
# secretary can extract sensible tasks from it.
_STUB_VIETNAMESE_TRANSCRIPT = """\
Cuộc họp nhóm ngày 15/6 giữa các thành viên. Trưởng nhóm tóm tắt: tuần này phải hoàn thành\
 phần thiết kế database, cần Lê Văn C phụ trách viết tài liệu API trước thứ 6. Phạm Thị D sẽ\
 làm giao diện trang chủ trên Figma, deadline cuối tuần. Hoàng Văn E phụ trách tích hợp\
 thanh toán VNPay, cần test với sandbox trước khi go-live. Cuối cùng nhóm sẽ họp lại vào\
 thứ 2 tuần sau để review tiến độ.
"""


async def transcribe_audio(file_path: Path) -> str:
    """Transcribe an audio file.  Returns transcript text.

    Args:
        file_path: path to the audio file (mp3/wav/m4a/mp4).

    Returns:
        The transcript text.  Falls back to a Vietnamese stub when
        ``OPENAI_API_KEY`` is not configured or the call fails.
    """
    if not settings.OPENAI_API_KEY:
        logger.info("OPENAI_API_KEY missing - using stub transcript for %s", file_path)
        return _STUB_VIETNAMESE_TRANSCRIPT

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        with file_path.open("rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model=settings.WHISPER_MODEL,
                file=audio_file,
                language="vi",
                response_format="text",
            )
        # When response_format="text" the SDK returns a string
        if isinstance(transcript, str):
            return transcript
        # Some SDK versions return an object with a .text attr
        return getattr(transcript, "text", str(transcript))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Whisper call failed (%s) - using stub", exc)
        return _STUB_VIETNAMESE_TRANSCRIPT
