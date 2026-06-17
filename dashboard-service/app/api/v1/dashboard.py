"""สรุปจำนวนคำร้องสำหรับหน้า dashboard — รับ `province_id` ตรงจาก query param

ไม่มี permission/scope check ในตัว service นี้เอง (ตั้งใจ) — เหมือน pattern ของ
`case-service/app/api/v1/case_for_staff.py::list_cases_for_staff` ทุกประการ:
caller (BFF) ส่ง province_id/district_id/current_status_id ที่ "อนุญาตแล้ว" มาตรง ๆ
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_session
from ...schemas import (
    DashboardDistrictRow,
    DashboardDistrictsRead,
    DashboardNationalOverviewRead,
    DashboardOverviewRead,
    DashboardProvinceRow,
    DashboardProvincesRead,
    DashboardStatusCount,
)
from ...settings import settings
from ...queries import (
    fetch_active_current_statuses,
    fetch_districts_page,
    fetch_districts_status_breakdown,
    fetch_districts_total_count,
    fetch_national_status_counts,
    fetch_national_total,
    fetch_overview_status_counts,
    fetch_overview_total,
    fetch_province,
    fetch_provinces_page,
    fetch_provinces_status_breakdown,
    fetch_provinces_total_count,
)

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


def _clean_ids(ids: list[int] | None) -> list[int] | None:
    """list ว่าง (`?type_money_id=` ไม่ระบุค่า) ให้ถือว่าไม่ได้กรอง เหมือน None."""
    return ids or None


async def _require_province(session: AsyncSession, province_id: int) -> dict:
    province = await fetch_province(session, province_id)
    if province is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="province_not_found")
    return province


@router.get("/national/overview", response_model=DashboardNationalOverviewRead)
async def get_national_overview(
    type_money_id: list[int] | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> DashboardNationalOverviewRead:
    """สรุปทั้งประเทศ แยกตาม status — ใช้ทำ donut chart ระดับประเทศ."""
    type_money_ids = _clean_ids(type_money_id)
    total = await fetch_national_total(session, type_money_ids=type_money_ids)
    status_rows = await fetch_national_status_counts(session, type_money_ids=type_money_ids)
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
    current_status_id: list[int] | None,
    type_money_id: list[int] | None,
    page: int,
    page_size: int,
    _prefetched_total: int | None = None,
) -> DashboardProvincesRead:
    current_status_ids = _clean_ids(current_status_id)
    type_money_ids = _clean_ids(type_money_id)

    total_items = _prefetched_total if _prefetched_total is not None else await fetch_provinces_total_count(session)
    total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else 1

    province_rows = await fetch_provinces_page(
        session,
        current_status_ids=current_status_ids,
        type_money_ids=type_money_ids,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    province_ids = [r["province_id"] for r in province_rows]

    breakdown_rows = await fetch_provinces_status_breakdown(
        session,
        province_ids=province_ids,
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
    current_status_id: list[int] | None = Query(None),
    type_money_id: list[int] | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1),
    session: AsyncSession = Depends(get_session),
) -> DashboardProvincesRead:
    """ตารางรายจังหวัดทั้งประเทศ แยกตาม status — มี pagination."""
    resolved = min(page_size or settings.default_page_size, settings.max_page_size)
    return await _build_provinces_response(
        session,
        current_status_id=current_status_id,
        type_money_id=type_money_id,
        page=page,
        page_size=resolved,
    )


@router.get("/provinces/export")
async def export_provinces(
    current_status_id: list[int] | None = Query(None),
    type_money_id: list[int] | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Excel รายจังหวัดทั้งประเทศ — ไม่มี pagination."""
    from openpyxl import Workbook
    from urllib.parse import quote

    total = await fetch_provinces_total_count(session)
    data = await _build_provinces_response(
        session,
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
    safe = "dashboard-national-provinces.xlsx"
    utf8 = quote("dashboard-ทั้งประเทศ-รายจังหวัด.xlsx")
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
