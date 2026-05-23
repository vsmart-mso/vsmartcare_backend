from __future__ import annotations

from ..province_summary import province_total_plain_line
from .context import StaffDigestContext


def build_plain_text(ctx: StaffDigestContext) -> str:
    lines = [
        f"เรียน {ctx.greeting_name}",
        "",
        "สรุปจำนวนคำร้องสวัสดิการในจังหวัดของท่าน ณ วันที่ " + (ctx.digest_date or "-"),
    ]
    if ctx.position:
        lines.append(f"ตำแหน่ง: {ctx.position}")
    if ctx.province_name:
        lines.append(f"จังหวัด: {ctx.province_name}")
        province_total = province_total_plain_line(ctx.province_name, ctx.total_applicants)
        if province_total:
            lines.append(province_total)

    lines.extend(
        [
            "",
            f"{ctx.highlight_label}: {ctx.highlight_count} รายการ",
            f"{ctx.emergency_label}: {ctx.emergency_count} รายการ",
            "(คำร้องเร่งด่วน: applicants.is_emergency = true ใน bucket ของท่าน)",
        ]
    )

    if ctx.tracking_url:
        lines.extend(["", f"เข้าสู่ระบบ พม. CARE: {ctx.tracking_url}"])

    lines.extend(["", "ขอแสดงความนับถือ", "พม. CARE"])
    return "\n".join(lines)
