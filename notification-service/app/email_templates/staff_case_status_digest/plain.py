from __future__ import annotations

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

    lines.extend(
        [
            "",
            f"{ctx.highlight_label}: {ctx.highlight_count} รายการ",
            "",
            f"รอรับเรื่อง (นักสังคม): {ctx.social_worker_pending}",
            f"รออนุมัติ (พมจ.): {ctx.pmj_pending_approve}",
            f"รอเบิก (การเงิน): {ctx.finance_pending}",
            f"คำร้องทั้งหมดในจังหวัด: {ctx.total_applicants}",
        ]
    )

    if ctx.tracking_url:
        lines.extend(["", f"เข้าสู่ระบบ พม. CARE: {ctx.tracking_url}"])

    lines.extend(["", "ขอแสดงความนับถือ", "พม. CARE"])
    return "\n".join(lines)
