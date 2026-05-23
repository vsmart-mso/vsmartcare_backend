from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..thai_date import format_thai_date
from ..welfare_status_updated.context import resolve_tracking_url

StaffDigestRole = Literal["social_worker", "pmj", "finance"]


@dataclass(frozen=True)
class StaffDigestContext:
    staff_name: str
    position: str
    province_name: str
    total_applicants: int
    digest_date: str
    role: StaffDigestRole
    highlight_label: str
    highlight_count: int
    emergency_label: str
    emergency_count: int
    tracking_url: str

    @property
    def greeting_name(self) -> str:
        return self.staff_name or "เจ้าหน้าที่"

    @property
    def highlight_count_text(self) -> str:
        return str(self.highlight_count)

    @property
    def emergency_count_text(self) -> str:
        return str(self.emergency_count)


_ROLE_ALIASES: dict[str, StaffDigestRole] = {
    "social_worker": "social_worker",
    "socialworker": "social_worker",
    "pmj": "pmj",
    "finance": "finance",
    "นักสังคม": "social_worker",
    "นักสังคมสงเคราะห์": "social_worker",
    "พมจ": "pmj",
    "พม.จ.": "pmj",
    "การเงิน": "finance",
}


def _parse_role(raw: object | None) -> StaffDigestRole:
    if raw is None:
        return "social_worker"
    text = str(raw).strip()
    if text in _ROLE_ALIASES:
        return _ROLE_ALIASES[text]
    compact = text.lower().replace(" ", "").replace(".", "")
    return _ROLE_ALIASES.get(compact, "social_worker")


def parse_payload(payload: dict[str, Any]) -> StaffDigestContext:
    role = _parse_role(payload.get("role"))
    return StaffDigestContext(
        staff_name=str(payload.get("staff_name") or payload.get("full_name") or ""),
        position=str(payload.get("position") or ""),
        province_name=str(payload.get("province_name") or ""),
        total_applicants=int(payload.get("total_applicants") or 0),
        digest_date=format_thai_date(payload.get("digest_date")),
        role=role,
        highlight_label=str(payload.get("highlight_label") or ""),
        highlight_count=int(payload.get("highlight_count") or 0),
        emergency_label=str(payload.get("emergency_label") or ""),
        emergency_count=int(payload.get("emergency_count") or 0),
        tracking_url=resolve_tracking_url(payload.get("tracking_url")),
    )
