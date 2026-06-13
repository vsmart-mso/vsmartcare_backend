"""Audit log สำหรับนักสังคมฯ แก้ไขข้อมูลคำร้อง — ตาราง case_data_edit_logs."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.case_data_edit_log import CaseDataEditLog

EVENT_TYPE_SECTION_EDIT = "section_edit"
EVENT_TYPE_SURVEY_EDIT = "survey_edit"

_SECTION_2_FIELDS = frozenset({
    "addresses",
    "dependency_loads",
    "economic_infos",
    "household_members",
})
_SECTION_3_FIELDS = frozenset({"welfare_history"})
_SECTION_4_FIELDS = frozenset({
    "problem_details",
    "request_type_ids",
    "request_other_text",
    "request_in_kind_text",
})

_SECTION_LABELS = {
    2: "ส่วนที่ 2: ที่อยู่อาศัย ครอบครัว และรายได้",
    3: "ส่วนที่ 3: สิทธิสวัสดิการที่เคยได้รับ",
    4: "ส่วนที่ 4: สภาพปัญหาและความต้องการความช่วยเหลือ",
    "survey": "ผลการเยี่ยมบ้าน",
}


def _sections_from_payload(payload: dict) -> list[int]:
    sections: list[int] = []
    keys = {k for k in payload if k != "update_by_sdshv"}
    if keys & _SECTION_2_FIELDS:
        sections.append(2)
    if keys & _SECTION_3_FIELDS:
        sections.append(3)
    if keys & _SECTION_4_FIELDS:
        sections.append(4)
    return sorted(sections)


def _sections_to_csv(sections: list[int] | None) -> str | None:
    if not sections:
        return None
    return ",".join(str(n) for n in sorted(sections))


def build_staff_section_edit_remarks(payload: dict) -> str:
    """สร้าง remarks จากฟิลด์ที่ส่งมาใน StaffCaseSectionsUpdate."""
    sections = _sections_from_payload(payload)
    if not sections:
        return "นักสังคมฯ แก้ไขข้อมูลปสค.1"
    labels = [_SECTION_LABELS[n] for n in sections]
    return "นักสังคมฯ แก้ไขปสค.1 — " + ", ".join(labels)


def build_staff_section_edit_sections(payload: dict) -> list[int]:
    return _sections_from_payload(payload)


def build_staff_survey_edit_remarks() -> str:
    return f"นักสังคมฯ แก้ไขปสค.1 — {_SECTION_LABELS['survey']}"


async def record_staff_data_edit_audit(
    session: AsyncSession,
    *,
    applicant_id: int,
    current_status_id: int,
    edit_by_sdshv: str | None,
    remarks: str,
    event_type: str,
    sections: list[int] | None = None,
) -> CaseDataEditLog:
    """บันทึก timeline การแก้ไข — ไม่แตะ welfare_request_status."""
    log = CaseDataEditLog(
        applicant_id=applicant_id,
        current_status_id_at_edit=current_status_id,
        edit_by_sdshv=(edit_by_sdshv or "").strip() or None,
        event_type=event_type,
        sections=_sections_to_csv(sections),
        remarks=remarks,
    )
    session.add(log)
    await session.flush()
    return log
