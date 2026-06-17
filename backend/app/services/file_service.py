"""File-serving helpers used by the meeting/audio preview endpoints.

We store everything in ``settings.UPLOAD_DIR`` and keep a relative
``file_url`` in the DB.  These helpers resolve that path, do MIME
sniffing, and stream the bytes back with optional HTTP Range support
so that ``<audio>`` / ``<video>`` and PDF viewers can seek.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional, Tuple

from fastapi import HTTPException


# Conservative mapping for the most common previewable formats.  The
# stdlib ``mimetypes`` module is unreliable on Windows.
_MIME = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def detect_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _MIME:
        return _MIME[ext]
    # Fall back to stdlib
    mt, _ = mimetypes.guess_type(str(path))
    return mt or "application/octet-stream"


def resolve_uploaded_file(file_url: Optional[str]) -> Path:
    """Translate a DB-stored ``file_url`` into an absolute path.

    The path is rejected if it escapes ``settings.UPLOAD_DIR`` to
    prevent path-traversal attacks.
    """
    from app.config import settings

    if not file_url:
        raise HTTPException(status_code=404, detail="No file associated with this meeting")
    base = settings.UPLOAD_DIR.parent.resolve()
    candidate = (base / file_url).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid file path") from exc
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return candidate


def parse_range_header(
    range_header: Optional[str], file_size: int
) -> Optional[Tuple[int, int]]:
    """Parse a single-range Range header.

    Returns ``(start, end)`` (inclusive on both ends) or ``None`` if
    the header is absent / malformed / unsupported.
    """
    if not range_header or not range_header.startswith("bytes="):
        return None
    spec = range_header[len("bytes="):].strip()
    if "," in spec:  # multi-range, not supported
        return None
    start_s, _, end_s = spec.partition("-")
    try:
        if start_s == "":
            # suffix range: last N bytes
            suffix_len = int(end_s)
            if suffix_len <= 0:
                return None
            start = max(0, file_size - suffix_len)
            end = file_size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else file_size - 1
    except ValueError:
        return None
    if start < 0 or end < start or start >= file_size:
        return None
    end = min(end, file_size - 1)
    return start, end
