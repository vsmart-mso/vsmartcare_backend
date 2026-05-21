from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...settings import settings
from .colors import StatusBoxStyle, resolve_status_box_style


def _normalize_portal_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        return ""
    return cleaned if cleaned.endswith("/") else f"{cleaned}/"


def resolve_tracking_url(payload_value: object | None) -> str:
    """payload.tracking_url ชนะ env FRONTEND_URL."""
    explicit = str(payload_value or "").strip()
    if explicit:
        return _normalize_portal_url(explicit)
    return _normalize_portal_url(settings.frontend_url)


@dataclass(frozen=True)
class WelfareStatusContext:
    status_label: str
    remarks: str
    case_ref: str
    tracking_url: str
    citizen_name: str
    status_box: StatusBoxStyle

    @property
    def greeting_name(self) -> str:
        return self.citizen_name or "ผู้ยื่นคำร้อง"

    @property
    def plain_greeting(self) -> str:
        return f"เรียน {self.citizen_name}" if self.citizen_name else "เรียน ผู้ยื่นคำร้อง"


def parse_payload(payload: dict[str, Any]) -> WelfareStatusContext:
    color_raw = payload.get("current_status_color")
    return WelfareStatusContext(
        status_label=str(payload.get("status_label") or ""),
        remarks=str(payload.get("remarks") or ""),
        case_ref=str(payload.get("case_ref") or ""),
        tracking_url=resolve_tracking_url(payload.get("tracking_url")),
        citizen_name=str(payload.get("person_name") or payload.get("citizen_name") or ""),
        status_box=resolve_status_box_style(str(color_raw) if color_raw else None),
    )
