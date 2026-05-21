from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WelfareStatusContext:
    status_label: str
    remarks: str
    case_ref: str
    tracking_url: str
    citizen_name: str

    @property
    def greeting_name(self) -> str:
        return self.citizen_name or "ผู้ยื่นคำร้อง"

    @property
    def plain_greeting(self) -> str:
        return f"เรียน {self.citizen_name}" if self.citizen_name else "เรียน ผู้ยื่นคำร้อง"


def parse_payload(payload: dict[str, Any]) -> WelfareStatusContext:
    return WelfareStatusContext(
        status_label=str(payload.get("status_label") or ""),
        remarks=str(payload.get("remarks") or ""),
        case_ref=str(payload.get("case_ref") or ""),
        tracking_url=str(payload.get("tracking_url") or ""),
        citizen_name=str(payload.get("citizen_name") or ""),
    )
