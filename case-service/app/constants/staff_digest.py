"""ค่าคงที่สำหรับสรุปสถานะคำร้องรายวัน (staff digest)."""

from __future__ import annotations

from typing import Final, Literal

from .current_status import CURRENT_STATUS_WITHDRAWING

StaffDigestRole = Literal["social_worker", "pmj", "finance"]

# รอรับเรื่อง
CURRENT_STATUS_PENDING_INTAKE: Final[int] = 1

# อยู่ระหว่างการเบิก — id 3 หลังอนุมัติพมจ., id 10 หลังบันทึกผลจ่าย 037 (description_staff เดียวกัน)
CURRENT_STATUS_WITHDRAWING_APPROVED: Final[int] = 3
CURRENT_STATUS_WITHDRAWING_IDS: Final[tuple[int, ...]] = (
    CURRENT_STATUS_WITHDRAWING_APPROVED,
    CURRENT_STATUS_WITHDRAWING,
)

ROLE_HIGHLIGHT_LABEL: dict[StaffDigestRole, str] = {
    "social_worker": "รอรับเรื่อง",
    "pmj": "รออนุมัติ",
    "finance": "รอการเบิกจ่าย",
}

ROLE_SUMMARY_FIELD: dict[StaffDigestRole, str] = {
    "social_worker": "social_worker_pending",
    "pmj": "pmj_pending_approve",
    "finance": "finance_pending",
}

ROLE_EMERGENCY_FIELD: dict[StaffDigestRole, str] = {
    "social_worker": "social_worker_emergency",
    "pmj": "pmj_emergency",
    "finance": "finance_emergency",
}

ROLE_EMERGENCY_LABEL: dict[StaffDigestRole, str] = {
    "social_worker": "คำร้องเร่งด่วน (รอรับเรื่อง)",
    "pmj": "คำร้องเร่งด่วน (รออนุมัติ)",
    "finance": "คำร้องเร่งด่วน (รอการเบิกจ่าย)",
}

TEMPLATE_CODE_STAFF_DIGEST: Final[str] = "STAFF_CASE_STATUS_DIGEST"
