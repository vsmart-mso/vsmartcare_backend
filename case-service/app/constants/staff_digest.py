"""ค่าคงที่สำหรับสรุปสถานะคำร้องรายวัน (staff digest)."""

from __future__ import annotations

from typing import Final, Literal

StaffDigestRole = Literal["social_worker", "pmj", "finance"]

CURRENT_STATUS_SOCIAL_WORKER: Final[int] = 1
CURRENT_STATUS_PMJ: Final[int] = 2
CURRENT_STATUS_FINANCE: Final[int] = 3

ROLE_HIGHLIGHT_LABEL: dict[StaffDigestRole, str] = {
    "social_worker": "รอรับเรื่อง",
    "pmj": "รออนุมัติ",
    "finance": "รอเบิก",
}

ROLE_SUMMARY_FIELD: dict[StaffDigestRole, str] = {
    "social_worker": "social_worker_pending",
    "pmj": "pmj_pending_approve",
    "finance": "finance_pending",
}

TEMPLATE_CODE_STAFF_DIGEST: Final[str] = "STAFF_CASE_STATUS_DIGEST"
