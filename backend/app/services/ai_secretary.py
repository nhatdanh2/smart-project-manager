"""LLM Agent 1 — AI Secretary.

Extracts tasks from a meeting transcript using Anthropic's Claude API.
Falls back to a deterministic stub when ``ANTHROPIC_API_KEY`` is
missing or every retry fails.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List

from app.config import settings


logger = logging.getLogger(__name__)


SECRETARY_SYSTEM_PROMPT = """Bạn là thư ký AI chuyên xử lý biên bản họp nhóm của sinh viên Việt Nam.

Nhiệm vụ: Đọc nội dung cuộc họp và trích xuất các công việc (tasks) cần làm.

Quy tắc trích xuất:
1. Mỗi task phải có: title, assignee (tên người được giao), deadline, story_points
2. story_points: 1=dễ/nhanh (<2h), 2=trung bình (2-4h), 3=khó (4-8h), 5=rất khó (>8h)
3. Nếu không rõ deadline, đặt là null
4. Nếu không rõ assignee, đặt là null
5. Chỉ trích xuất task cụ thể, không trích xuất thảo luận chung

QUAN TRỌNG: Chỉ trả về JSON array, không có text nào khác (không ```, không giải thích).

Output format (JSON array):
[
  {
    "title": "Tên công việc cụ thể",
    "description": "Mô tả chi tiết nếu có",
    "assignee_name": "Tên thành viên hoặc null",
    "deadline_text": "Chuỗi deadline như '15/7' hoặc 'tuần sau' hoặc null",
    "story_points": 2,
    "depends_on_titles": ["Tên task phụ thuộc nếu có"]
  }
]
"""


# -----------------------------------------------------------------------------
# Stub fallback
# -----------------------------------------------------------------------------
def _stub_extract(content: str, project_members: List[str]) -> List[Dict[str, Any]]:
    """Heuristic fallback used when no API key is configured or LLM fails."""
    sentences = re.split(r"(?<=[.!?\n])\s+", content)
    tasks: List[Dict[str, Any]] = []
    action_words = ("phải", "cần", "sẽ", "làm", "triển khai", "chuẩn bị", "hoàn thành", "gửi", "thiết kế")
    for idx, sent in enumerate(sentences):
        sent = sent.strip()
        if len(sent) < 8 or len(sent) > 220:
            continue
        if not any(w in sent.lower() for w in action_words):
            continue
        assignee = project_members[idx % len(project_members)] if project_members else None
        tasks.append(
            {
                "title": sent[:120],
                "description": sent,
                "assignee_name": assignee,
                "deadline_text": None,
                "story_points": 2,
                "depends_on_titles": [],
            }
        )
        if len(tasks) >= 6:
            break
    if not tasks:
        tasks.append(
            {
                "title": "Xem lại nội dung cuộc họp",
                "description": content[:240],
                "assignee_name": project_members[0] if project_members else None,
                "deadline_text": None,
                "story_points": 1,
                "depends_on_titles": [],
            }
        )
    return tasks


# -----------------------------------------------------------------------------
# Robust JSON extraction
# -----------------------------------------------------------------------------
def _coerce_to_list(parsed: Any) -> List[Dict[str, Any]]:
    """Some models wrap the array in an object (``{"tasks": [...]}``)."""
    if isinstance(parsed, list):
        return [p for p in parsed if isinstance(p, dict)]
    if isinstance(parsed, dict):
        for key in ("tasks", "items", "data", "extracted_tasks"):
            if key in parsed and isinstance(parsed[key], list):
                return [p for p in parsed[key] if isinstance(p, dict)]
    return []


def _extract_json(text: str) -> List[Dict[str, Any]]:
    """Best-effort JSON extraction with multiple fallbacks.

    Handles:
    * ``\`\`\`json … \`\`\`` fences
    * Pre-/post-amble around the JSON array
    * Single object returned instead of an array
    * Truncated JSON (tries to close the array)
    """
    if not text:
        raise ValueError("empty text from model")

    cleaned = text.strip()
    # Strip code fences
    cleaned = re.sub(r"^```(?:json|JSON)?\s*", "", cleaned).strip()
    cleaned = re.sub(r"\s*```\s*$", "", cleaned).strip()

    # Try the whole text first
    try:
        return _coerce_to_list(json.loads(cleaned))
    except Exception:
        pass

    # Find the first '[' and matching ']' — naive bracket match
    start = cleaned.find("[")
    if start == -1:
        # Maybe it returned a single object
        obj_start = cleaned.find("{")
        obj_end = cleaned.rfind("}")
        if obj_start != -1 and obj_end > obj_start:
            try:
                return _coerce_to_list(json.loads(cleaned[obj_start : obj_end + 1]))
            except Exception:
                pass
        raise ValueError("no JSON array/object in response")

    end = cleaned.rfind("]")
    if end == -1 or end <= start:
        # JSON was truncated — try to close it
        truncated = cleaned[start:].rstrip(",\n ") + "]"
        return _coerce_to_list(json.loads(truncated))

    return _coerce_to_list(json.loads(cleaned[start : end + 1]))


def _validate_task(t: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize one task dict — coerce types, fill defaults."""
    title = (t.get("title") or "").strip()
    if not title:
        return None  # type: ignore[return-value]
    sp = t.get("story_points", 1)
    try:
        sp = int(sp)
    except Exception:
        sp = 1
    sp = max(1, min(sp, 5))
    depends = t.get("depends_on_titles") or []
    if not isinstance(depends, list):
        depends = []
    return {
        "title": title[:255],
        "description": (t.get("description") or "").strip()[:2000],
        "assignee_name": (t.get("assignee_name") or None) and str(t.get("assignee_name")).strip(),
        "deadline_text": (t.get("deadline_text") or None) and str(t.get("deadline_text")).strip(),
        "story_points": sp,
        "depends_on_titles": [str(d) for d in depends if d],
    }


def _normalize(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in raw:
        cleaned = _validate_task(r)
        if cleaned:
            out.append(cleaned)
    return out


# -----------------------------------------------------------------------------
# Claude call with retry
# -----------------------------------------------------------------------------
async def _call_claude(content: str, project_members: List[str]) -> List[Dict[str, Any]]:
    """Call Claude, retry on JSON parse failures.

    On a parse failure we append a follow-up message asking for pure
    JSON, which usually fixes truncated / explanatory responses.
    """
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    user_message = (
        f"Danh sách thành viên nhóm: {', '.join(project_members) or '(không rõ)'}\n\n"
        f"Nội dung cuộc họp:\n---\n{content}\n---\n\n"
        "Hãy trích xuất tất cả công việc được phân công trong cuộc họp này."
    )

    last_error: Exception | None = None
    messages: List[Dict[str, Any]] = [{"role": "user", "content": user_message}]

    for attempt in range(3):
        try:
            msg = await client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2048,
                system=SECRETARY_SYSTEM_PROMPT,
                messages=messages,
            )
            text_blocks = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
            if not text_blocks:
                raise ValueError("Claude returned no text content")
            try:
                parsed = _extract_json(text_blocks[0])
                if not parsed:
                    raise ValueError("empty task list after parse")
                return _normalize(parsed)
            except (ValueError, json.JSONDecodeError) as parse_err:
                last_error = parse_err
                logger.warning(
                    "ai_secretary parse failed on attempt %d: %s",
                    attempt + 1,
                    parse_err,
                )
                # On retry, add a follow-up: "Give me strict JSON"
                messages.append({"role": "assistant", "content": text_blocks[0]})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Phản hồi trên không phải JSON hợp lệ. Hãy trả về ĐÚNG một JSON array, "
                            "không ```json, không giải thích, không kèm text nào khác."
                        ),
                    }
                )
                # Exponential backoff
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
        except Exception as exc:  # noqa: BLE001 — network/SDK errors
            last_error = exc
            logger.warning("ai_secretary Claude call failed on attempt %d: %s", attempt + 1, exc)
            await asyncio.sleep(0.5 * (2 ** attempt))

    raise last_error or RuntimeError("ai_secretary: all retries failed")


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
async def extract_tasks_from_meeting(
    content: str, project_members: List[str]
) -> List[Dict[str, Any]]:
    """Extract tasks from a meeting transcript.

    Strategy:
    1. If no API key → stub
    2. Else call Claude with up to 3 retries; on each parse failure
       the model is asked to "return strict JSON only" and we back
       off exponentially.
    3. On any unrecoverable error → stub (never block the user).
    """
    if not settings.ANTHROPIC_API_KEY:
        logger.info("ANTHROPIC_API_KEY missing — using stub extractor")
        return _stub_extract(content, project_members)
    try:
        return await _call_claude(content, project_members)
    except Exception as exc:  # noqa: BLE001
        logger.exception("ai_secretary failed (%s) — falling back to stub", exc)
        return _stub_extract(content, project_members)
