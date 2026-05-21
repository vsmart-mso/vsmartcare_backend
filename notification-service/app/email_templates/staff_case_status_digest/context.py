from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..welfare_status_updated.context import resolve_tracking_url


@dataclass(frozen=True)
class StaffDigestContext:
    staff_name: str
    position: str
    province_name: str
    digest_date: str
    highlight_label: str
    highlight_count: int
    social_worker_pending: int
    pmj_pending_approve: int
    finance_pending: int
    total_applicants: int
    tracking_url: str

    @property
    def greeting_name(self) -> str:
        return self.staff_name or "เจ้าหน้าที่"

    @property
    def highlight_count_text(self) -> str:
        return str(self.highlight_count)


def parse_payload(payload: dict[str, Any]) -> StaffDigestContext:
    return StaffDigestContext(
        staff_name=str(payload.get("staff_name") or payload.get("full_name") or ""),
        position=str(payload.get("position") or ""),
        province_name=str(payload.get("province_name") or ""),
        digest_date=str(payload.get("digest_date") or ""),
        highlight_label=str(payload.get("highlight_label") or ""),
        highlight_count=int(payload.get("highlight_count") or 0),
        social_worker_pending=int(payload.get("social_worker_pending") or 0),
        pmj_pending_approve=int(payload.get("pmj_pending_approve") or 0),
        finance_pending=int(payload.get("finance_pending") or 0),
        total_applicants=int(payload.get("total_applicants") or 0),
        tracking_url=resolve_tracking_url(payload.get("tracking_url")),
    )
