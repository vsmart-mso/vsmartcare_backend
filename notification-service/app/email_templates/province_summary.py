"""บล็อกสรุปจำนวนคำร้องทั้งหมดในจังหวัด — ใช้ร่วมทุกเทมเพลตอีเมล."""

from __future__ import annotations

from typing import Any

from .loader import fill, load_html


def parse_province_total(payload: dict[str, Any]) -> tuple[str, int]:
    province_name = str(payload.get("province_name") or "").strip()
    total = payload.get("total_applicants")
    if total is None:
        total = payload.get("province_total_applicants")
    try:
        total_applicants = int(total or 0)
    except (TypeError, ValueError):
        total_applicants = 0
    return province_name, total_applicants


def province_total_html_block(province_name: str, total_applicants: int) -> str:
    if not province_name:
        return ""
    return fill(
        load_html("fragments/province_total.html"),
        province_name=province_name,
        total_applicants=str(total_applicants),
    )


def province_total_plain_line(province_name: str, total_applicants: int) -> str:
    if not province_name:
        return ""
    return f"คำร้องทั้งหมดในจังหวัด{province_name}: {total_applicants} รายการ"
