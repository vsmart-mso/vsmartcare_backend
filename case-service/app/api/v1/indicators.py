"""Indicators API — สรุปเงินช่วยเหลือ พม Care 6 ประเภท."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_session
from ...schemas.indicators import (
    IndicatorCaseStatus,
    IndicatorsByProvinceResponse,
    IndicatorsExportResponse,
    IndicatorsNationwideResponse,
)
from ...services.indicators_summary import (
    fetch_indicators_by_province,
    fetch_indicators_export,
    fetch_indicators_nationwide,
)

router = APIRouter(prefix="/v1/indicators", tags=["indicators"])

BudgetYearParam = Annotated[
    int,
    Query(
        ge=2500,
        le=2700,
        description="ปีงบประมาณ พ.ศ. (เช่น 2568) — รอบ 1 ต.ค. – 30 ก.ย.",
    ),
]

CaseStatusParam = Annotated[
    IndicatorCaseStatus,
    Query(
        description=(
            "เลือกสถานะที่นับ — "
            "`aided`=ช่วยเหลือแล้ว (status 4), "
            "`forwarded`=ส่งต่อแล้ว (status 11); default=`aided`"
        ),
    ),
]


@router.get(
    "/by-province",
    response_model=IndicatorsByProvinceResponse,
    summary="ตัวชี้วัดเงินช่วยเหลือรายจังหวัด ตามประเภทเงินพม Care",
    description=(
        "สรุปเงิน/จำนวนเคสแยก 6 ประเภทเงินของจังหวัดที่เลือก — "
        "แต่ละประเภทมี by_regulation (ระเบียบเงิน) และ by_approver_sdshv (ผู้อนุมัติจาก approve_case); "
        "เลือก `case_status=aided|forwarded`; "
        "สค. (type 6) นับที่จังหวัดแม่ตาม DWF (`drpod_dwf.json`); ประเภท 1–5 นับตามที่อยู่เคส"
    ),
)
async def get_indicators_by_province(
    budget_year: BudgetYearParam,
    province_id: int = Query(..., ge=1, description="รหัสจังหวัด"),
    case_status: CaseStatusParam = IndicatorCaseStatus.aided,
    session: AsyncSession = Depends(get_session),
) -> IndicatorsByProvinceResponse:
    summary = await fetch_indicators_by_province(
        session,
        province_id,
        budget_year,
        case_status=case_status,
    )
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="province_not_found")
    return summary


@router.get(
    "/nationwide",
    response_model=IndicatorsNationwideResponse,
    summary="ตัวชี้วัดเงินช่วยเหลือครบทุกจังหวัด (ไม่แยกประเภทเงิน)",
    description=(
        "สรุปเงิน/จำนวนเคสรายจังหวัด (ไม่แยกหมวด) — "
        "เลือก `case_status=aided|forwarded`; "
        "สค. (type 6) จัดเข้าจังหวัดแม่ตาม DWF; จังหวัดลูกได้ สค. = 0 ในหมวดนี้"
    ),
)
async def get_indicators_nationwide(
    budget_year: BudgetYearParam,
    province_id: list[int] | None = Query(
        None,
        description="กรองเฉพาะจังหวัดที่ระบุ — ส่งซ้ำได้หลายค่า; ไม่ส่ง = ครบทุกจังหวัด",
    ),
    case_status: CaseStatusParam = IndicatorCaseStatus.aided,
    session: AsyncSession = Depends(get_session),
) -> IndicatorsNationwideResponse:
    return await fetch_indicators_nationwide(
        session,
        budget_year,
        province_ids=province_id,
        case_status=case_status,
    )


@router.get(
    "/export",
    response_model=IndicatorsExportResponse,
    summary="Export ตัวชี้วัดเงินช่วยเหลือเป็น JSON แถวต่อเคส",
    description=(
        "คืนรายการเคสที่เข้าเกณฑ์ indicators ตาม `case_status` "
        "(aided=ช่วยเหลือแล้ว 4, forwarded=ส่งต่อแล้ว 11), "
        "aided_at ในปีงบ, ประเภทเงิน 1–6 "
        "เป็น JSON แถวต่อเคสให้ frontend map เข้าเทมเพลต Excel — "
        "สค. นับที่จังหวัดแม่ตาม DWF; ไม่รวมรหัสหน่วยงาน/เลขที่รับ (ปล่อยให้ FE ว่างในเทมเพลต)"
    ),
)
async def get_indicators_export(
    budget_year: BudgetYearParam,
    province_id: list[int] | None = Query(
        None,
        description="กรองด้วย effective_province — ส่งซ้ำได้หลายค่า",
    ),
    type_money_category_id: list[int] | None = Query(
        None,
        description="กรองประเภทเงิน — ส่งซ้ำได้; ไม่ส่ง = 1–6",
    ),
    regulation_id: list[int] | None = Query(
        None,
        description="กรองระเบียบ — ส่งซ้ำได้; ไม่ส่ง = ทุกระเบียบ",
    ),
    case_status: CaseStatusParam = IndicatorCaseStatus.aided,
    session: AsyncSession = Depends(get_session),
) -> IndicatorsExportResponse:
    return await fetch_indicators_export(
        session,
        budget_year,
        province_ids=province_id,
        type_money_category_ids=type_money_category_id,
        regulation_ids=regulation_id,
        case_status=case_status,
    )
