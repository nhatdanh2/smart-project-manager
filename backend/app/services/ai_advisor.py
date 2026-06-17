"""LLM Agent 2 — AI Advisor.

Generates a Vietnamese project status report for instructors.
Falls back to a deterministic template when no API key is set or
every retry fails.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List

from app.config import settings


logger = logging.getLogger(__name__)


ADVISOR_SYSTEM_PROMPT = """Bạn là cố vấn AI phân tích tiến độ đồ án nhóm sinh viên.

Vai trò: Tạo báo cáo khách quan, ngắn gọn (~200-300 từ) cho giảng viên về tình hình thực tế của nhóm.

Ngôn ngữ: Tiếng Việt, chuyên nghiệp nhưng dễ hiểu.

Cấu trúc báo cáo bắt buộc:
1. **Tình hình tổng quan** (2-3 câu): Dự án có nguy cơ trễ không? Tiến độ chung thế nào?
2. **Phân tích đóng góp** (3-5 câu): Ai đang làm việc nhiều nhất/ít nhất? Có sự mất cân bằng không?
3. **Cảnh báo đỏ** (nếu có): Chỉ đưa ra nếu có vấn đề nghiêm trọng (ai đó không đóng góp >7 ngày, critical path trễ, v.v.)
4. **Đề xuất** (1-2 câu): Giảng viên nên chú ý điều gì?

QUAN TRỌNG:
- Dựa HOÀN TOÀN vào dữ liệu được cung cấp, không phán đoán chủ quan
- Dùng tên cụ thể của sinh viên, không dùng 'thành viên A'
- Nếu dữ liệu không đủ để kết luận, nói rõ điều đó
- Mỗi phản đoán phải dẫn nguồn: "vì X ngày không có hoạt động", "vì Y task quá hạn", v.v.

Trả về Markdown thuần (không kèm giải thích ngoài báo cáo)."""


# -----------------------------------------------------------------------------
# Stub fallback
# -----------------------------------------------------------------------------
def _format_member(m: Dict[str, Any]) -> str:
    return (
        f"- {m.get('name')}: {m.get('contribution_percent', 0):.1f}% đóng góp | "
        f"hoàn thành {m.get('tasks_completed', 0)}/{m.get('tasks_assigned', 0)} task | "
        f"đúng hạn {int(m.get('on_time_rate', 0) * 100)}% | "
        f"hoạt động gần nhất: {m.get('last_activity_days_ago', 'không rõ')} ngày trước"
    )


def _stub_report(project_data: Dict[str, Any]) -> str:
    title = project_data.get("project_title", "Dự án")
    deadline = project_data.get("deadline", "—")
    days_remaining = project_data.get("days_remaining", "—")
    completed = project_data.get("completed_tasks", 0)
    total = project_data.get("total_tasks", 0)
    overdue = project_data.get("overdue_tasks", 0)
    delay_risk = project_data.get("delay_risk", 0.0)
    members: List[Dict[str, Any]] = project_data.get("members", [])
    critical = project_data.get("critical_path_tasks", [])

    progress_pct = int((completed / total) * 100) if total else 0

    risk_text = (
        "rất cao, cần can thiệp ngay"
        if delay_risk >= 0.7
        else "đáng chú ý"
        if delay_risk >= 0.3
        else "thấp, nhóm đang kiểm soát tốt"
    )

    ghosts = [m for m in members if m.get("is_ghost")]
    gansh = [m for m in members if m.get("contribution_percent", 0) >= 40]
    least = sorted(members, key=lambda m: m.get("contribution_percent", 0))[:2]

    lines: List[str] = []
    lines.append(f"# Báo cáo AI — {title}")
    lines.append("")
    lines.append("## 1. Tình hình tổng quan")
    lines.append(
        f"Dự án còn {days_remaining} ngày đến deadline ({deadline}). "
        f"Tiến độ hiện tại: {completed}/{total} task hoàn thành ({progress_pct}%), "
        f"{overdue} task đã quá hạn. Nguy cơ trễ hạn được đánh giá ở mức **{risk_text}** "
        f"(điểm rủi ro CPM: {delay_risk:.2f})."
    )
    lines.append("")
    lines.append("## 2. Phân tích đóng góp")
    if not members:
        lines.append("_Chưa có dữ liệu thành viên để phân tích._")
    else:
        if gansh:
            names = ", ".join(m["name"] for m in gansh)
            lines.append(f"- Thành viên đang **gánh team**: {names}.")
        if least:
            names = ", ".join(m["name"] for m in least)
            lines.append(f"- Thành viên đóng góp thấp nhất: {names}.")
        lines.append("- Chi tiết:")
        for m in members:
            lines.append(_format_member(m))
    lines.append("")
    lines.append("## 3. Cảnh báo đỏ")
    if not ghosts and not critical:
        lines.append("_Không có cảnh báo nghiêm trọng._")
    else:
        if ghosts:
            names = ", ".join(m["name"] for m in ghosts)
            lines.append(
                f"- **{names}** không có hoạt động cập nhật nào trong hơn 7 ngày — "
                "nguy cơ 'ghost member'."
            )
        if critical:
            lines.append(
                f"- Có {len(critical)} task nằm trên **critical path**. "
                "Bất kỳ task nào trễ sẽ ảnh hưởng trực tiếp đến deadline."
            )
    lines.append("")
    lines.append("## 4. Đề xuất")
    if delay_risk >= 0.3 or ghosts:
        lines.append(
            "Giảng viên nên hẹn gặp nhóm trong tuần này để rà soát lại critical path "
            "và nhắc nhở các thành viên đang chậm cập nhật."
        )
    else:
        lines.append(
            "Tiến độ hiện tại ổn; giảng viên có thể tiếp tục theo dõi và nhắc nhở nhẹ vào cuối tuần."
        )
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Markdown validation — keep only what looks like a real report
# -----------------------------------------------------------------------------
def _looks_like_report(text: str) -> bool:
    if not text or len(text) < 80:
        return False
    # Must contain at least one markdown heading and one bullet/list marker
    return ("##" in text or "**" in text) and len(text) > 100


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("\n", 1)
        text = parts[1] if len(parts) == 2 else ""
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


# -----------------------------------------------------------------------------
# Pretty-print project data for the LLM
# -----------------------------------------------------------------------------
def _format_user_payload(project_data: Dict[str, Any]) -> str:
    """Render the project dict as a human-readable text block."""
    lines: List[str] = []
    lines.append(f"Tên dự án: {project_data.get('project_title', '—')}")
    lines.append(f"Deadline: {project_data.get('deadline', '—')} (còn {project_data.get('days_remaining', '—')} ngày)")
    lines.append(
        f"Task: {project_data.get('completed_tasks', 0)}/{project_data.get('total_tasks', 0)} hoàn thành, "
        f"{project_data.get('overdue_tasks', 0)} quá hạn"
    )
    lines.append(f"CPM delay risk: {project_data.get('delay_risk', 0.0):.2f}")
    cp = project_data.get("critical_path_tasks") or []
    if cp:
        lines.append("Critical path: " + ", ".join(t.get("title", "?") for t in cp))
    members = project_data.get("members") or []
    if members:
        lines.append("Thành viên:")
        for m in members:
            lines.append(_format_member(m))
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Claude call with retry
# -----------------------------------------------------------------------------
async def _call_claude(project_data: Dict[str, Any]) -> str:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    user_message = (
        "Dữ liệu dự án:\n" + _format_user_payload(project_data)
        + "\n\nHãy viết báo cáo theo đúng 4 mục trong system prompt."
    )

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            msg = await client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=1500,
                system=ADVISOR_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            text_blocks = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
            if not text_blocks:
                raise ValueError("Claude returned no text content")
            cleaned = _strip_code_fence(text_blocks[0])
            if not _looks_like_report(cleaned):
                raise ValueError(f"report failed sanity check: len={len(cleaned)}")
            return cleaned
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning("ai_advisor attempt %d failed: %s", attempt + 1, exc)
            await asyncio.sleep(0.5 * (2 ** attempt))
    raise last_error or RuntimeError("ai_advisor: all retries failed")


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
async def generate_project_report(project_data: Dict[str, Any]) -> str:
    """Generate a Vietnamese project status report."""
    if not settings.ANTHROPIC_API_KEY:
        logger.info("ANTHROPIC_API_KEY missing — using stub advisor")
        return _stub_report(project_data)
    try:
        return await _call_claude(project_data)
    except Exception as exc:  # noqa: BLE001
        logger.exception("ai_advisor failed (%s) — using stub", exc)
        return _stub_report(project_data)
