from __future__ import annotations

from .context import WelfareStatusContext

SUBJECT_BASE = "แจ้งอัปเดตสถานะคำร้องสวัสดิการ"


def build_subject(ctx: WelfareStatusContext) -> str:
    subject = SUBJECT_BASE
    if ctx.case_ref:
        subject += f" ({ctx.case_ref})"
    return subject
