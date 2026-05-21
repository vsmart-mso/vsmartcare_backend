from __future__ import annotations

from .context import StaffDigestContext


def build_subject(ctx: StaffDigestContext) -> str:
    date_part = f" ({ctx.digest_date})" if ctx.digest_date else ""
    province_part = f" — {ctx.province_name}" if ctx.province_name else ""
    return f"สรุปคำร้องรายวัน{date_part}{province_part}"
