"""สรุปจำนวนคำร้องสำหรับหน้า dashboard — รับ `province_id` ตรงจาก query param

ไม่มี permission/scope check ในตัว service นี้เอง (ตั้งใจ) — เหมือน pattern ของ
`case-service/app/api/v1/case_for_staff.py::list_cases_for_staff` ทุกประการ:
caller (BFF) ส่ง province_id/district_id/current_status_id ที่ "อนุญาตแล้ว" มาตรง ๆ
"""

from __future__ import annotations

import io
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_session
from ...schemas import (
    DashboardCaseRow,
    DashboardCasesRead,
    DashboardDistrictRow,
    DashboardDistrictsRead,
    DashboardNationalOverviewRead,
    DashboardOverviewRead,
    DashboardProvinceRow,
    DashboardProvincesRead,
    DashboardStatusCount,
    DashboardSubDistrictRow,
    DashboardSubDistrictsRead,
)
from ...settings import settings
from ...queries import (
    DashboardCaseFilters,
    fetch_active_current_statuses,
    fetch_dashboard_cases_count,
    fetch_dashboard_cases_page,
    fetch_district,
    fetch_districts_page,
    fetch_districts_status_breakdown,
    fetch_districts_total_count,
    fetch_existing_province_ids,
    fetch_national_status_counts,
    fetch_national_total,
    fetch_overview_status_counts,
    fetch_overview_total,
    fetch_province,
    fetch_provinces_page,
    fetch_provinces_status_breakdown,
    fetch_provinces_total_count,
    fetch_sub_districts_page,
    fetch_sub_districts_status_breakdown,
    fetch_sub_districts_total_count,
)

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


def _clean_ids(ids: list[int] | None) -> list[int] | None:
    """list ว่าง (`?type_money_id=` ไม่ระบุค่า) ให้ถือว่าไม่ได้กรอง เหมือน None."""
    return ids or None


def _clean_text_filter(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


_BANGKOK = ZoneInfo("Asia/Bangkok")


def _sla_fields(
    started_at: datetime | None,
    sla_days: int | None,
    *,
    completed_at: datetime | None,
    frozen_elapsed: int | None,
) -> dict:
    """คำนวณฟิลด์ SLA ให้สอดคล้อง case-service `process_sla_fields_dict`."""
    empty = {
        "process_started_at": started_at,
        "process_completed_at": completed_at,
        "process_sla_days": sla_days,
        "process_elapsed_days": None,
        "process_remaining_days": None,
        "process_traffic_color": None,
        "process_is_overdue": None,
        "time_count_process": None,
    }
    if sla_days is None:
        return empty

    def _now_bangkok(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(tz=_BANGKOK)
        if value.tzinfo is None:
            return value.replace(tzinfo=_BANGKOK)
        return value.astimezone(_BANGKOK)

    def _elapsed(start: datetime, end: datetime | None) -> int:
        end_bkk = _now_bangkok(end)
        start_bkk = start.astimezone(_BANGKOK) if start.tzinfo else start.replace(tzinfo=_BANGKOK)
        return (end_bkk.date() - start_bkk.date()).days

    def _traffic(elapsed: int, sla: int) -> str:
        if sla == 10:
            if elapsed <= 4:
                return "green"
            if elapsed <= 7:
                return "yellow"
            if elapsed <= 10:
                return "orange"
            return "red"
        if sla == 15:
            if elapsed <= 5:
                return "green"
            if elapsed <= 11:
                return "yellow"
            if elapsed <= 15:
                return "orange"
            return "red"
        if sla <= 0:
            return "red"
        pct = elapsed / sla
        if pct <= 0.40:
            return "green"
        if pct <= 0.70:
            return "yellow"
        if pct <= 1.0:
            return "orange"
        return "red"

    if started_at is None:
        if completed_at is not None and frozen_elapsed is not None:
            remaining = sla_days - frozen_elapsed
            return {
                "process_started_at": started_at,
                "process_completed_at": completed_at,
                "process_sla_days": sla_days,
                "process_elapsed_days": frozen_elapsed,
                "process_remaining_days": remaining,
                "process_traffic_color": _traffic(frozen_elapsed, sla_days),
                "process_is_overdue": remaining < 0,
                "time_count_process": frozen_elapsed,
            }
        return empty

    elapsed = _elapsed(started_at, completed_at)
    remaining = sla_days - elapsed
    return {
        "process_started_at": started_at,
        "process_completed_at": completed_at,
        "process_sla_days": sla_days,
        "process_elapsed_days": elapsed,
        "process_remaining_days": remaining,
        "process_traffic_color": _traffic(elapsed, sla_days),
        "process_is_overdue": remaining < 0,
        "time_count_process": elapsed,
    }


def _row_to_dashboard_case(row: dict) -> DashboardCaseRow:
    completed_at = row.get("process_completed_at")
    frozen = row.get("time_count_process") if completed_at is not None else None
    row.update(
        _sla_fields(
            row.get("process_started_at"),
            row.get("process_sla_days"),
            completed_at=completed_at,
            frozen_elapsed=frozen if isinstance(frozen, int) else None,
        )
    )
    row["current_address_province_id"] = row.get("province_id")
    row["current_address_province_name"] = row.get("province_name")
    row["person_age"] = int(row.get("person_age") or 0)
    row["count_037"] = int(row.get("count_037") or 0)
    row["count_038"] = int(row.get("count_038") or 0)
    row.setdefault("prior_self_submit_case_numbers", [])
    row.setdefault("self_submit_fiscal_year_count", 0)
    row.setdefault("self_submit_fiscal_year_case_numbers", [])
    row.setdefault("responsible_division_name", None)

    sources = row.get("existing_case_detected_sources")
    if sources is not None and not isinstance(sources, list):
        row["existing_case_detected_sources"] = None

    require_ktb = bool(row.get("require_ktb_corporate", True))
    source = row.get("existing_case_source")
    ref_id = row.get("existing_case_ref_id")
    prior_reuse = None
    if not require_ktb and source in {"VCARE", "Legacy"} and ref_id is not None:
        prior_reuse = int(ref_id)
    row["prior_ktb_reuse_applicant_id"] = prior_reuse
    return DashboardCaseRow.model_validate(row)


async def _require_province(session: AsyncSession, province_id: int) -> dict:
    province = await fetch_province(session, province_id)
    if province is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="province_not_found")
    return province


# 77 = จำนวนจังหวัดทั้งประเทศ — ส่งเกินนี้แปลว่า caller ส่งอะไรผิดแน่ ๆ
MAX_PROVINCE_FILTER = 77


async def _validate_province_ids(
    session: AsyncSession, province_id: list[int] | None
) -> list[int] | None:
    """ตรวจ `province_id` หลายค่าก่อนใช้กรอง — ห้ามเมิน param แล้วคืนข้อมูลทั้งประเทศ

    ไม่ส่งมา (หรือส่งมาว่าง) = ไม่กรอง คืน None ตามพฤติกรรมเดิม
    ส่งมาแล้วมีค่าผิด ต้อง error พร้อมบอกว่าค่าไหนผิด เพื่อให้ caller debug ได้
    """
    ids = _clean_ids(province_id)
    if ids is None:
        return None

    unique_ids = sorted(set(ids))
    if len(unique_ids) > MAX_PROVINCE_FILTER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"too_many_province_id: ส่งมา {len(unique_ids)} ค่า "
                f"เกินที่รองรับ {MAX_PROVINCE_FILTER} ค่า"
            ),
        )

    existing = await fetch_existing_province_ids(session, unique_ids)
    missing = [pid for pid in unique_ids if pid not in existing]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"province_not_found: {missing}",
        )
    return unique_ids


@router.get("/national/overview", response_model=DashboardNationalOverviewRead)
async def get_national_overview(
    province_id: list[int] | None = Query(
        None, description="กรองเฉพาะจังหวัดที่ระบุ ส่งซ้ำได้หลายค่า ไม่ส่ง = ทุกจังหวัด"
    ),
    current_status_id: list[int] | None = Query(
        None, description="กรองตาม current_status_id ได้หลายค่า"
    ),
    type_money_id: list[int] | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> DashboardNationalOverviewRead:
    """สรุปทั้งประเทศ (หรือเฉพาะจังหวัดที่ระบุ) แยกตาม status — ใช้ทำ donut chart."""
    province_ids = await _validate_province_ids(session, province_id)
    current_status_ids = _clean_ids(current_status_id)
    type_money_ids = _clean_ids(type_money_id)
    total = await fetch_national_total(
        session,
        province_ids=province_ids,
        current_status_ids=current_status_ids,
        type_money_ids=type_money_ids,
    )
    status_rows = await fetch_national_status_counts(
        session,
        province_ids=province_ids,
        current_status_ids=current_status_ids,
        type_money_ids=type_money_ids,
    )
    statuses = [
        DashboardStatusCount(
            current_status_id=row["current_status_id"],
            label=row["label"],
            color=row["color"],
            count=row["count"],
            percent=round((row["count"] / total * 100), 1) if total else 0.0,
        )
        for row in status_rows
    ]
    return DashboardNationalOverviewRead(
        total=total,
        updated_at=datetime.now(timezone.utc),
        statuses=statuses,
    )


async def _build_provinces_response(
    session: AsyncSession,
    *,
    province_ids: list[int] | None,
    current_status_id: list[int] | None,
    type_money_id: list[int] | None,
    page: int,
    page_size: int,
    _prefetched_total: int | None = None,
) -> DashboardProvincesRead:
    current_status_ids = _clean_ids(current_status_id)
    type_money_ids = _clean_ids(type_money_id)

    # total_items/total_pages ต้องนับจากชุดที่กรองแล้ว ไม่ใช่ 77 จังหวัดเสมอ
    total_items = (
        _prefetched_total
        if _prefetched_total is not None
        else await fetch_provinces_total_count(session, province_ids=province_ids)
    )
    total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else 1

    province_rows = await fetch_provinces_page(
        session,
        province_ids=province_ids,
        current_status_ids=current_status_ids,
        type_money_ids=type_money_ids,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    page_province_ids = [r["province_id"] for r in province_rows]

    breakdown_rows = await fetch_provinces_status_breakdown(
        session,
        province_ids=page_province_ids,
        current_status_ids=current_status_ids,
        type_money_ids=type_money_ids,
    )
    status_counts_by_province: dict[int, dict[str, int]] = {}
    for row in breakdown_rows:
        status_counts_by_province.setdefault(row["province_id"], {})[
            str(row["current_status_id"])
        ] = row["count"]

    items = [
        DashboardProvinceRow(
            province_id=row["province_id"],
            province_name=row["province_name"],
            status_counts=status_counts_by_province.get(row["province_id"], {}),
            total=row["total"],
        )
        for row in province_rows
    ]
    return DashboardProvincesRead(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        items=items,
    )


@router.get("/provinces", response_model=DashboardProvincesRead)
async def get_provinces(
    province_id: list[int] | None = Query(
        None, description="กรองเฉพาะจังหวัดที่ระบุ ส่งซ้ำได้หลายค่า ไม่ส่ง = ทุกจังหวัด"
    ),
    current_status_id: list[int] | None = Query(None),
    type_money_id: list[int] | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1),
    session: AsyncSession = Depends(get_session),
) -> DashboardProvincesRead:
    """ตารางรายจังหวัด (ทั้งประเทศ หรือเฉพาะที่ระบุ) แยกตาม status — มี pagination."""
    resolved = min(page_size or settings.default_page_size, settings.max_page_size)
    province_ids = await _validate_province_ids(session, province_id)
    return await _build_provinces_response(
        session,
        province_ids=province_ids,
        current_status_id=current_status_id,
        type_money_id=type_money_id,
        page=page,
        page_size=resolved,
    )


@router.get("/provinces/export")
async def export_provinces(
    province_id: list[int] | None = Query(
        None, description="กรองเฉพาะจังหวัดที่ระบุ ส่งซ้ำได้หลายค่า ไม่ส่ง = ทุกจังหวัด"
    ),
    current_status_id: list[int] | None = Query(None),
    type_money_id: list[int] | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Excel รายจังหวัด (ทั้งประเทศ หรือเฉพาะที่ระบุ) — ไม่มี pagination."""
    from openpyxl import Workbook
    from urllib.parse import quote

    province_ids = await _validate_province_ids(session, province_id)
    total = await fetch_provinces_total_count(session, province_ids=province_ids)
    data = await _build_provinces_response(
        session,
        province_ids=province_ids,
        current_status_id=current_status_id,
        type_money_id=type_money_id,
        page=1,
        page_size=max(total, 1),
        _prefetched_total=total,
    )
    status_labels = await fetch_active_current_statuses(session)
    status_ids = [r["id"] for r in status_labels]
    status_headers = [r["label"] for r in status_labels]

    wb = Workbook()
    ws = wb.active
    ws.title = "provinces"
    ws.append(["ลำดับ", "จังหวัด", *status_headers, "รวม"])
    for idx, row in enumerate(data.items, start=1):
        ws.append([idx, row.province_name, *[row.status_counts.get(str(s), 0) for s in status_ids], row.total])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    # กรองจังหวัดแล้วอย่าตั้งชื่อไฟล์ว่า "ทั้งประเทศ" — ผู้ใช้ สสว. จะเข้าใจผิดว่าได้ข้อมูลครบ
    scope = "ทั้งประเทศ" if province_ids is None else f"{len(province_ids)}-จังหวัด"
    safe = "dashboard-national-provinces.xlsx" if province_ids is None else "dashboard-provinces.xlsx"
    utf8 = quote(f"dashboard-{scope}-รายจังหวัด.xlsx")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe}"; filename*=UTF-8\'\'{utf8}'},
    )


@router.get("/overview", response_model=DashboardOverviewRead)
async def get_overview(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการดู"),
    type_money_id: list[int] | None = Query(
        None, description="กรองตาม type_money_category.id ได้หลายค่า"
    ),
    session: AsyncSession = Depends(get_session),
) -> DashboardOverviewRead:
    province = await _require_province(session, province_id)
    type_money_ids = _clean_ids(type_money_id)

    total = await fetch_overview_total(
        session, province_id=province_id, type_money_ids=type_money_ids
    )
    status_rows = await fetch_overview_status_counts(
        session, province_id=province_id, type_money_ids=type_money_ids
    )

    statuses = [
        DashboardStatusCount(
            current_status_id=row["current_status_id"],
            label=row["label"],
            color=row["color"],
            count=row["count"],
            percent=round((row["count"] / total * 100), 1) if total else 0.0,
        )
        for row in status_rows
    ]

    return DashboardOverviewRead(
        province_id=province["id"],
        province_name=province["name"],
        total=total,
        updated_at=datetime.now(timezone.utc),
        statuses=statuses,
    )


async def _build_districts_response(
    session: AsyncSession,
    *,
    province_id: int,
    current_status_id: list[int] | None,
    type_money_id: list[int] | None,
    page: int,
    page_size: int,
    _prefetched_total: int | None = None,
) -> DashboardDistrictsRead:
    province = await _require_province(session, province_id)
    current_status_ids = _clean_ids(current_status_id)
    type_money_ids = _clean_ids(type_money_id)

    total_items = _prefetched_total if _prefetched_total is not None else await fetch_districts_total_count(session, province_id=province_id)
    total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else 1

    district_rows = await fetch_districts_page(
        session,
        province_id=province_id,
        current_status_ids=current_status_ids,
        type_money_ids=type_money_ids,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    district_ids = [r["district_id"] for r in district_rows]

    breakdown_rows = await fetch_districts_status_breakdown(
        session,
        province_id=province_id,
        district_ids=district_ids,
        current_status_ids=current_status_ids,
        type_money_ids=type_money_ids,
    )
    status_counts_by_district: dict[int, dict[str, int]] = {}
    for row in breakdown_rows:
        status_counts_by_district.setdefault(row["district_id"], {})[
            str(row["current_status_id"])
        ] = row["count"]

    items = [
        DashboardDistrictRow(
            district_id=row["district_id"],
            district_code=row.get("district_code"),
            district_name=row["district_name"],
            status_counts=status_counts_by_district.get(row["district_id"], {}),
            total=row["total"],
        )
        for row in district_rows
    ]

    return DashboardDistrictsRead(
        province_id=province["id"],
        province_name=province["name"],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        items=items,
    )


@router.get("/districts", response_model=DashboardDistrictsRead)
async def get_districts(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการดู"),
    current_status_id: list[int] | None = Query(
        None, description="กรองตาม current_status_id ได้หลายค่า"
    ),
    type_money_id: list[int] | None = Query(
        None, description="กรองตาม type_money_category.id ได้หลายค่า"
    ),
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1, description="ค่าเริ่มต้น/สูงสุดตั้งค่าผ่าน env"),
    session: AsyncSession = Depends(get_session),
) -> DashboardDistrictsRead:
    resolved_page_size = min(page_size or settings.default_page_size, settings.max_page_size)
    return await _build_districts_response(
        session,
        province_id=province_id,
        current_status_id=current_status_id,
        type_money_id=type_money_id,
        page=page,
        page_size=resolved_page_size,
    )


@router.get("/sub-districts", response_model=DashboardSubDistrictsRead)
async def get_sub_districts(
    district_id: int = Query(..., description="รหัสอำเภอที่ต้องการดู"),
    province_id: int = Query(..., description="รหัสจังหวัด (ตรวจสอบว่าอำเภออยู่ในจังหวัดนี้)"),
    current_status_id: list[int] | None = Query(None),
    type_money_id: list[int] | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1),
    session: AsyncSession = Depends(get_session),
) -> DashboardSubDistrictsRead:
    """ตารางรายตำบล แยกตาม status — คืนทุกตำบลในอำเภอ (แม้ count=0) พร้อม status_counts."""
    district = await fetch_district(session, district_id=district_id, province_id=province_id)
    if district is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="district_not_found")

    resolved_page_size = min(page_size or settings.default_page_size, settings.max_page_size)
    current_status_ids = _clean_ids(current_status_id)
    type_money_ids = _clean_ids(type_money_id)

    total_items = await fetch_sub_districts_total_count(session, district_id=district_id)
    total_pages = max(1, (total_items + resolved_page_size - 1) // resolved_page_size) if total_items else 1

    sub_district_rows = await fetch_sub_districts_page(
        session,
        district_id=district_id,
        province_id=province_id,
        current_status_ids=current_status_ids,
        type_money_ids=type_money_ids,
        limit=resolved_page_size,
        offset=(page - 1) * resolved_page_size,
    )
    sub_district_ids = [r["sub_district_id"] for r in sub_district_rows]

    breakdown_rows = await fetch_sub_districts_status_breakdown(
        session,
        district_id=district_id,
        province_id=province_id,
        sub_district_ids=sub_district_ids,
        current_status_ids=current_status_ids,
        type_money_ids=type_money_ids,
    )
    status_counts_by_sub_district: dict[int, dict[str, int]] = {}
    for row in breakdown_rows:
        status_counts_by_sub_district.setdefault(row["sub_district_id"], {})[
            str(row["current_status_id"])
        ] = row["count"]

    items = [
        DashboardSubDistrictRow(
            sub_district_id=row["sub_district_id"],
            sub_district_code=row.get("sub_district_code"),
            sub_district_name=row["sub_district_name"],
            status_counts=status_counts_by_sub_district.get(row["sub_district_id"], {}),
            total=row["total"],
        )
        for row in sub_district_rows
    ]

    return DashboardSubDistrictsRead(
        district_id=district["district_id"],
        district_name=district["district_name"],
        province_id=district["province_id"],
        province_name=district["province_name"],
        page=page,
        page_size=resolved_page_size,
        total_items=total_items,
        total_pages=total_pages,
        items=items,
    )


@router.get("/districts/export")
async def export_districts(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการดู"),
    current_status_id: list[int] | None = Query(None),
    type_money_id: list[int] | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Excel รายอำเภอ — filter เดียวกับ `/districts` แต่ดึงทุกอำเภอในจังหวัด (ไม่ pagination)."""
    from openpyxl import Workbook

    total_districts = await fetch_districts_total_count(session, province_id=province_id)
    data = await _build_districts_response(
        session,
        province_id=province_id,
        current_status_id=current_status_id,
        type_money_id=type_money_id,
        page=1,
        page_size=max(total_districts, 1),
        _prefetched_total=total_districts,
    )

    status_labels = await fetch_active_current_statuses(session)
    status_ids = [row["id"] for row in status_labels]
    status_headers = [row["label"] for row in status_labels]

    wb = Workbook()
    ws = wb.active
    ws.title = "districts"
    ws.append(["ลำดับ", "อำเภอ", *status_headers, "รวม"])
    for idx, row in enumerate(data.items, start=1):
        ws.append(
            [
                idx,
                row.district_name,
                *[row.status_counts.get(str(sid), 0) for sid in status_ids],
                row.total,
            ]
        )

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    # ชื่อจังหวัดเป็นภาษาไทย — header ASCII-only ใช้ filename สำรอง, ตัวจริง (UTF-8) ใช้ filename*
    # ตาม RFC 6266 เพื่อให้เบราว์เซอร์ถอดชื่อไฟล์ภาษาไทยได้ถูกต้อง
    from urllib.parse import quote

    safe_filename = f"dashboard-province-{province_id}-districts.xlsx"
    utf8_filename = quote(f"dashboard-{data.province_name}-districts.xlsx")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{utf8_filename}'
            )
        },
    )


@router.get("/cases", response_model=DashboardCasesRead)
async def get_cases(
    province_id: list[int] | None = Query(
        None, description="กรองเฉพาะจังหวัดที่ระบุ ส่งซ้ำได้หลายค่า ไม่ส่ง = ทุกจังหวัด"
    ),
    current_status_id: list[int] | None = Query(
        None, description="กรองตาม current_status_id ได้หลายค่า"
    ),
    type_money_id: list[int] | None = Query(
        None, description="กรองตาม type_money_category.id ได้หลายค่า"
    ),
    case_number: str | None = Query(None, description="ค้นหาจากเลข case"),
    current_status: str | None = Query(None, description="ค้นหาจากข้อความสถานะฝั่งเจ้าหน้าที่"),
    firstname: str | None = Query(None, description="ค้นหาจากชื่อ"),
    lastname: str | None = Query(None, description="ค้นหาจากนามสกุล"),
    cid: str | None = Query(None, description="ค้นหาจากเลขบัตรประชาชน"),
    datetime_create: date | None = Query(None, description="วันที่สร้าง case (YYYY-MM-DD)"),
    province_name: str | None = Query(None, description="ค้นหาจากชื่อจังหวัด"),
    district_id: int | None = Query(None, description="กรองตามอำเภอ"),
    district_name: str | None = Query(None, description="ค้นหาจากชื่ออำเภอ"),
    subdistrict_id: int | None = Query(None, description="กรองตามตำบล"),
    subdistrict_name: str | None = Query(None, description="ค้นหาจากชื่อตำบล"),
    subdistrict_postcode_id: int | None = Query(
        None, description="กรองตามแถว bridge sub_districts_postcode"
    ),
    postcode: str | None = Query(None, description="ค้นหาจากรหัสไปรษณีย์"),
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1),
    session: AsyncSession = Depends(get_session),
) -> DashboardCasesRead:
    """รายการคำร้องแบบ case_for_staff — ไม่ส่ง province_id = ทั้ง 77 จังหวัด มี pagination."""
    province_ids = await _validate_province_ids(session, province_id)
    resolved_page_size = min(page_size or settings.default_page_size, settings.max_page_size)
    filters = DashboardCaseFilters(
        province_ids=province_ids,
        current_status_ids=_clean_ids(current_status_id),
        type_money_ids=_clean_ids(type_money_id),
        case_number=_clean_text_filter(case_number),
        current_status=_clean_text_filter(current_status),
        firstname=_clean_text_filter(firstname),
        lastname=_clean_text_filter(lastname),
        cid=_clean_text_filter(cid),
        datetime_create=datetime_create,
        province_name=_clean_text_filter(province_name),
        district_id=district_id,
        district_name=_clean_text_filter(district_name),
        subdistrict_id=subdistrict_id,
        subdistrict_name=_clean_text_filter(subdistrict_name),
        subdistrict_postcode_id=subdistrict_postcode_id,
        postcode=_clean_text_filter(postcode),
    )
    total_items = await fetch_dashboard_cases_count(session, filters)
    total_pages = max(1, (total_items + resolved_page_size - 1) // resolved_page_size) if total_items else 1
    rows = await fetch_dashboard_cases_page(
        session,
        filters,
        limit=resolved_page_size,
        offset=(page - 1) * resolved_page_size,
    )
    return DashboardCasesRead(
        province_ids=province_ids,
        page=page,
        page_size=resolved_page_size,
        total_items=total_items,
        total_pages=total_pages,
        items=[_row_to_dashboard_case(row) for row in rows],
    )
