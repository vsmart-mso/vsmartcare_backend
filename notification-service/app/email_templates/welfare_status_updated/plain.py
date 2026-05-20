from __future__ import annotations

from .context import WelfareStatusContext


def build_plain_text(ctx: WelfareStatusContext) -> str:
    lines = [
        ctx.plain_greeting,
        "",
        "ระบบได้ดำเนินการอัปเดตสถานะคำร้องสวัสดิการของท่าน",
        f"สถานะปัจจุบัน: {ctx.status_label}",
    ]

    if ctx.case_ref:
        lines.append(f"เลขที่คำร้อง: {ctx.case_ref}")

    if ctx.remarks:
        lines.append(f"หมายเหตุ: {ctx.remarks}")

    if ctx.tracking_url:
        lines.extend(["", f"ตรวจสอบรายละเอียดเพิ่มเติม: {ctx.tracking_url}"])

    lines.extend(["", "ขอแสดงความนับถือ", "พม. CARE"])
    return "\n".join(lines)
