from __future__ import annotations

from .context import WelfareCaseSubmittedContext


def build_plain_text(ctx: WelfareCaseSubmittedContext) -> str:
    lines = [
        ctx.plain_greeting,
        "",
        ctx.intro,
        ctx.headline,
    ]

    if ctx.case_ref:
        lines.append(f"เลขที่คำร้อง: {ctx.case_ref}")

    if ctx.tracking_url:
        lines.extend(["", f"ตรวจสอบรายละเอียดเพิ่มเติม: {ctx.tracking_url}"])

    lines.extend(["", "ขอแสดงความนับถือ", "พม. CARE"])
    return "\n".join(lines)
