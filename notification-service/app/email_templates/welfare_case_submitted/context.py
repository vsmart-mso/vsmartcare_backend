from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ...settings import settings
from ..welfare_status_updated.colors import StatusBoxStyle, resolve_status_box_style

SubmissionKind = Literal["initial", "correction"]

_MESSAGES: dict[SubmissionKind, dict[str, str]] = {
    "initial": {
        "headline": "ท่านได้ดำเนินการ ส่งคำขอเรียบร้อยแล้ว",
        "intro": "ระบบได้รับคำร้องสวัสดิการของท่านเรียบร้อยแล้ว คำร้องจะอยู่ในสถานะรอรับเรื่อง",
    },
    "correction": {
        "headline": "ขอบคุณสำหรับการปรับแก้ไขข้อมูล",
        "intro": "ระบบได้รับข้อมูลที่ท่านปรับแก้ไขเรียบร้อยแล้ว คำร้องจะอยู่ในสถานะรอรับเรื่อง",
    },
}

_SUBJECTS: dict[SubmissionKind, str] = {
    "initial": "ยืนยันการส่งคำร้องสวัสดิการ",
    "correction": "ยืนยันการส่งข้อมูลที่แก้ไข",
}

_SUCCESS_COLOR = "#009f75"


def _normalize_portal_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        return ""
    return cleaned if cleaned.endswith("/") else f"{cleaned}/"


def resolve_tracking_url(payload_value: object | None) -> str:
    explicit = str(payload_value or "").strip()
    if explicit:
        return _normalize_portal_url(explicit)
    return _normalize_portal_url(settings.frontend_url)


def parse_submission_kind(raw: object | None) -> SubmissionKind:
    value = str(raw or "initial").strip().lower()
    if value == "correction":
        return "correction"
    return "initial"


@dataclass(frozen=True)
class WelfareCaseSubmittedContext:
    submission_kind: SubmissionKind
    headline: str
    intro: str
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


def parse_payload(payload: dict[str, Any]) -> WelfareCaseSubmittedContext:
    kind = parse_submission_kind(payload.get("submission_kind"))
    messages = _MESSAGES[kind]
    return WelfareCaseSubmittedContext(
        submission_kind=kind,
        headline=str(payload.get("headline") or messages["headline"]),
        intro=str(payload.get("intro") or messages["intro"]),
        case_ref=str(payload.get("case_ref") or ""),
        tracking_url=resolve_tracking_url(payload.get("tracking_url")),
        citizen_name=str(payload.get("person_name") or payload.get("citizen_name") or ""),
        status_box=resolve_status_box_style(_SUCCESS_COLOR),
    )


def build_subject_base(kind: SubmissionKind) -> str:
    return _SUBJECTS[kind]
