"""Payment intake API — หน้า 11 (รับเรื่อง), 13 (วิธีจ่ายเงิน), 20 (KTB Corporate).

Endpoints:
  GET  /v1/regulations                       — dropdown ระเบียบสำหรับหน้า 11
  GET  /v1/payment-methods                   — dropdown วิธีจ่ายเงินสำหรับหน้า 13
  POST /v1/cases/{applicant_id}/intake       — upsert หน้า 11 (case_handling + regulation_choice)
  GET  /v1/cases/{applicant_id}/intake       — ดูสถานะ intake ทั้งหมด
  PATCH /v1/cases/{applicant_id}/intake      — แก้ไขหน้า 11
  POST /v1/cases/{applicant_id}/intake/payment   — upsert หน้า 13 (case_payment)
  GET  /v1/cases/{applicant_id}/intake/payment   — ดู case_payment
  PATCH /v1/cases/{applicant_id}/intake/payment  — แก้ไขหน้า 13
  POST /v1/cases/{applicant_id}/intake/ktb       — upsert หน้า 20 (case_ktb_corporate)
  GET  /v1/cases/{applicant_id}/intake/ktb       — ดู case_ktb_corporate
  PATCH /v1/cases/{applicant_id}/intake/ktb      — แก้ไขหน้า 20
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.database import get_session
from ...core.staff_security import require_staff
from ...models.applicant import Applicant
from ...models.intake import (
    AnnouncementRegulation,
    CaseHandling,
    CaseKtbCorporate,
    CasePayment,
    CaseRegulationChoice,
    PaymentMethod,
)
from ...models.lookup import BankName
from ...models.person import Person
from ...schemas.intake import (
    CaseHandlingRead,
    CaseIntakeRead,
    CaseKtbCorporateRead,
    CaseKtbCorporateUpsert,
    CasePaymentRead,
    CasePaymentUpsert,
    IntakeHandlingUpsert,
    PaymentMethodRead,
    RegulationDropdownItem,
    RegulationRead,
)

router = APIRouter(
    prefix="/v1/intake",
    tags=["intake"],
    dependencies=[Depends(require_staff)],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_applicant_or_404(session: AsyncSession, applicant_id: int) -> Applicant:
    row = await session.get(Applicant, applicant_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")
    return row


async def _get_handling_or_404(session: AsyncSession, applicant_id: int) -> CaseHandling:
    row = await session.scalar(
        select(CaseHandling)
        .where(CaseHandling.applicant_id == applicant_id)
        .options(
            selectinload(CaseHandling.regulation_choice).selectinload(
                CaseRegulationChoice.regulation
            )
        ),
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_handling_not_found")
    return row


def _regulation_display_name(reg: AnnouncementRegulation) -> str:
    if reg.short_name:
        return f"({reg.short_name}) {reg.name}"
    return reg.name


def _build_intake_read(applicant_id: int, handling: CaseHandling | None) -> CaseIntakeRead:
    if handling is None:
        return CaseIntakeRead(applicant_id=applicant_id, intake_completed=False)

    payment_read = (
        CasePaymentRead.model_validate(handling.payment) if handling.payment else None
    )
    ktb_read = (
        CaseKtbCorporateRead.model_validate(handling.ktb_corporate)
        if handling.ktb_corporate
        else None
    )
    return CaseIntakeRead(
        applicant_id=applicant_id,
        case_handling=CaseHandlingRead.model_validate(handling),
        payment=payment_read,
        ktb_corporate=ktb_read,
        intake_completed=handling.intake_completed_at is not None,
    )


async def _load_handling_full(session: AsyncSession, applicant_id: int) -> CaseHandling | None:
    return await session.scalar(
        select(CaseHandling)
        .where(CaseHandling.applicant_id == applicant_id)
        .options(
            selectinload(CaseHandling.regulation_choice).selectinload(
                CaseRegulationChoice.regulation
            ),
            selectinload(CaseHandling.payment).selectinload(CasePayment.payment_method),
            selectinload(CaseHandling.ktb_corporate),
            selectinload(CaseHandling.type_money),
        ),
    )


# ---------------------------------------------------------------------------
# Regulation dropdown — GET /v1/regulations
# ---------------------------------------------------------------------------


@router.get(
    "/regulations",
    response_model=list[RegulationDropdownItem],
    summary="รายการระเบียบสำหรับ dropdown หน้า 11",
    description=(
        "ดึงระเบียบที่ activate=true เรียงตาม sort_order — "
        "ถ้าส่ง citizen (CID) + budget_year จะคำนวณ count_used และ disabled ด้วย"
    ),
)
async def list_regulations(
    citizen: str | None = Query(None, max_length=13, description="เลขบัตรประชาชน 13 หลัก"),
    budget_year: int | None = Query(
        None, description="ปีงบประมาณไทย (พ.ศ.) เช่น 2568 — ใช้นับ count_used"
    ),
    session: AsyncSession = Depends(get_session),
) -> list[RegulationDropdownItem]:
    stmt = (
        select(AnnouncementRegulation)
        .where(AnnouncementRegulation.activate.is_(True))
        .order_by(
            AnnouncementRegulation.sort_order.asc().nullslast(),
            AnnouncementRegulation.id.asc(),
        )
    )

    regs = list((await session.execute(stmt)).scalars().all())

    # คำนวณ count_used ต่อ regulation สำหรับบุคคลนี้ในปีงบประมาณที่กำหนด
    usage_map: dict[int, int] = {}
    if citizen and budget_year:
        gregorian_year = budget_year - 543
        reg_ids = [r.id for r in regs]

        count_sq = (
            select(
                CaseRegulationChoice.regulation_id.label("reg_id"),
                func.count().label("cnt"),
            )
            .join(CaseHandling, CaseHandling.id == CaseRegulationChoice.case_handling_id)
            .join(Applicant, Applicant.id == CaseHandling.applicant_id)
            .join(Person, Person.id == Applicant.persons_id)
            .where(
                Person.cid == citizen,
                CaseRegulationChoice.regulation_id.in_(reg_ids),
                func.extract("year", CaseHandling.intake_completed_at) == gregorian_year,
            )
            .group_by(CaseRegulationChoice.regulation_id)
        )
        rows = (await session.execute(count_sq)).all()
        usage_map = {row.reg_id: row.cnt for row in rows}

    result: list[RegulationDropdownItem] = []
    for reg in regs:
        count = usage_map.get(reg.id, 0)
        disabled = reg.limit_per_budget_year > 0 and count >= reg.limit_per_budget_year
        result.append(
            RegulationDropdownItem(
                id=reg.id,
                code=reg.code,
                name=reg.name,
                display_name=_regulation_display_name(reg),
                type_money_category_id=reg.type_money_category_id,
                type_money_category_name_acronym=reg.type_money_category.name_acronym,
                maximum_money=reg.maximum_money,
                limit_per_budget_year=reg.limit_per_budget_year,
                activate=reg.activate,
                count_used=count,
                disabled=disabled,
            )
        )
    return result


# ---------------------------------------------------------------------------
# Regulation detail — GET /v1/regulations/{regulation_id}
# ---------------------------------------------------------------------------


@router.get(
    "/regulations/{regulation_id}",
    response_model=RegulationRead,
    summary="รายละเอียดระเบียบ",
)
async def get_regulation(
    regulation_id: int,
    session: AsyncSession = Depends(get_session),
) -> RegulationRead:
    row = await session.get(AnnouncementRegulation, regulation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="regulation_not_found")
    return RegulationRead.model_validate(row)


# ---------------------------------------------------------------------------
# Payment methods — GET /v1/payment-methods
# ---------------------------------------------------------------------------


@router.get(
    "/payment-methods",
    response_model=list[PaymentMethodRead],
    summary="รายการวิธีจ่ายเงินสำหรับ dropdown หน้า 13",
)
async def list_payment_methods(
    session: AsyncSession = Depends(get_session),
) -> list[PaymentMethodRead]:
    rows = list(
        (
            await session.execute(
                select(PaymentMethod).order_by(PaymentMethod.sort_order.asc())
            )
        )
        .scalars()
        .all()
    )
    return [PaymentMethodRead.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /v1/cases/{applicant_id}/intake — สถานะ intake ทั้งหมด
# ---------------------------------------------------------------------------


@router.get(
    "/cases/{applicant_id}",
    response_model=CaseIntakeRead,
    summary="ดูสถานะ intake ทั้งหมด (หน้า 11, 13, 20)",
)
async def get_intake(
    applicant_id: int,
    session: AsyncSession = Depends(get_session),
) -> CaseIntakeRead:
    await _get_applicant_or_404(session, applicant_id)
    handling = await _load_handling_full(session, applicant_id)
    return _build_intake_read(applicant_id, handling)


# ---------------------------------------------------------------------------
# POST /v1/cases/{applicant_id}/intake — บันทึก/แก้ไข หน้า 11
# ---------------------------------------------------------------------------


@router.post(
    "/cases/{applicant_id}",
    response_model=CaseIntakeRead,
    status_code=status.HTTP_201_CREATED,
    summary="บันทึกข้อมูลหน้า 11 (eleven_insert) — upsert case_handling + regulation_choice",
    description=(
        "ถ้ายังไม่มี case_handling → สร้างใหม่ ถ้ามีแล้ว → อัปเดต\n"
        "Side effects: อัปเดต applicants.type_money_category_id ตาม regulation ที่เลือก"
    ),
)
async def upsert_intake_handling(
    applicant_id: int,
    body: IntakeHandlingUpsert = Body(...),
    session: AsyncSession = Depends(get_session),
) -> CaseIntakeRead:
    applicant = await _get_applicant_or_404(session, applicant_id)

    reg = await session.get(AnnouncementRegulation, body.regulation_id)
    if reg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="regulation_not_found"
        )
    if not reg.activate:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="regulation_not_active",
        )

    # อัปเดต applicants.type_money_category_id ตาม regulation ที่เลือก
    if applicant.type_money_category_id != reg.type_money_category_id:
        applicant.type_money_category_id = reg.type_money_category_id

    # Upsert case_handling
    handling = await session.scalar(
        select(CaseHandling).where(CaseHandling.applicant_id == applicant_id)
    )
    if handling is None:
        handling = CaseHandling(
            applicant_id=applicant_id,
            vsmart_informer_id=body.vsmart_informer_id,
            vsmart_social_worker_id=body.vsmart_social_worker_id,
            sw_user_sdshv=body.sw_user_sdshv,
            type_money_id=body.type_money_id,
        )
        session.add(handling)
        await session.flush()
    else:
        if body.vsmart_informer_id is not None:
            handling.vsmart_informer_id = body.vsmart_informer_id
        if body.vsmart_social_worker_id is not None:
            handling.vsmart_social_worker_id = body.vsmart_social_worker_id
        if body.sw_user_sdshv is not None:
            handling.sw_user_sdshv = body.sw_user_sdshv
        if body.type_money_id is not None:
            handling.type_money_id = body.type_money_id
        handling.updated_at = datetime.utcnow()

    # Upsert case_regulation_choice
    choice = await session.scalar(
        select(CaseRegulationChoice).where(
            CaseRegulationChoice.case_handling_id == handling.id
        )
    )
    if choice is None:
        choice = CaseRegulationChoice(
            case_handling_id=handling.id,
            regulation_id=body.regulation_id,
            help_kind=body.help_kind,
            money_amount=body.money_amount,
            comment=body.comment,
            esignature=body.esignature,
            signed_by_sdshv=body.signed_by_sdshv,
        )
        session.add(choice)
    else:
        choice.regulation_id = body.regulation_id
        choice.help_kind = body.help_kind
        choice.money_amount = body.money_amount
        choice.comment = body.comment
        choice.esignature = body.esignature
        choice.signed_by_sdshv = body.signed_by_sdshv
        choice.updated_at = datetime.utcnow()

    await session.commit()
    reloaded = await _load_handling_full(session, applicant_id)
    return _build_intake_read(applicant_id, reloaded)


# ---------------------------------------------------------------------------
# PATCH /v1/cases/{applicant_id}/intake — แก้ไขหน้า 11 (alias → POST)
# ---------------------------------------------------------------------------


@router.patch(
    "/cases/{applicant_id}",
    response_model=CaseIntakeRead,
    summary="แก้ไขข้อมูลหน้า 11 (เหมือน POST แต่ต้องมี case_handling อยู่แล้ว)",
)
async def patch_intake_handling(
    applicant_id: int,
    body: IntakeHandlingUpsert = Body(...),
    session: AsyncSession = Depends(get_session),
) -> CaseIntakeRead:
    # ตรวจว่ามี case_handling อยู่แล้ว
    await _get_handling_or_404(session, applicant_id)
    return await upsert_intake_handling(applicant_id, body, session)


# ---------------------------------------------------------------------------
# POST /v1/cases/{applicant_id}/intake/payment — บันทึกวิธีจ่ายเงินหน้า 13
# ---------------------------------------------------------------------------


@router.post(
    "/cases/{applicant_id}/payment",
    response_model=CasePaymentRead,
    status_code=status.HTTP_201_CREATED,
    summary="บันทึกวิธีจ่ายเงินหน้า 13 (thirteen_insert) — upsert case_payment",
)
async def upsert_intake_payment(
    applicant_id: int,
    body: CasePaymentUpsert = Body(...),
    session: AsyncSession = Depends(get_session),
) -> CasePaymentRead:
    handling = await _get_handling_or_404(session, applicant_id)

    pm = await session.get(PaymentMethod, body.payment_method_id)
    if pm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="payment_method_not_found"
        )

    if body.bank_name_id is not None:
        if await session.get(BankName, body.bank_name_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="bank_name_not_found"
            )

    if body.agent_person_id is not None:
        if await session.get(Person, body.agent_person_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="agent_person_not_found"
            )

    if body.payee_person_id is not None:
        if await session.get(Person, body.payee_person_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="payee_person_not_found"
            )

    payment = await session.scalar(
        select(CasePayment)
        .where(CasePayment.case_handling_id == handling.id)
        .options(selectinload(CasePayment.payment_method)),
    )

    fields = body.model_dump()
    if payment is None:
        payment = CasePayment(case_handling_id=handling.id, **fields)
        session.add(payment)
    else:
        for k, v in fields.items():
            setattr(payment, k, v)
        payment.updated_at = datetime.utcnow()

    # อัปเดต intake_completed_at เมื่อบันทึกการจ่ายเงินครั้งแรก
    if handling.intake_completed_at is None:
        handling.intake_completed_at = datetime.utcnow()

    await session.commit()

    reloaded = await session.scalar(
        select(CasePayment)
        .where(CasePayment.id == payment.id)
        .options(selectinload(CasePayment.payment_method)),
    )
    return CasePaymentRead.model_validate(reloaded)


# ---------------------------------------------------------------------------
# GET /v1/cases/{applicant_id}/intake/payment
# ---------------------------------------------------------------------------


@router.get(
    "/cases/{applicant_id}/payment",
    response_model=CasePaymentRead,
    summary="ดูข้อมูลวิธีจ่ายเงิน (case_payment)",
)
async def get_intake_payment(
    applicant_id: int,
    session: AsyncSession = Depends(get_session),
) -> CasePaymentRead:
    handling = await _get_handling_or_404(session, applicant_id)
    payment = await session.scalar(
        select(CasePayment)
        .where(CasePayment.case_handling_id == handling.id)
        .options(selectinload(CasePayment.payment_method)),
    )
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="case_payment_not_found"
        )
    return CasePaymentRead.model_validate(payment)


# ---------------------------------------------------------------------------
# PATCH /v1/cases/{applicant_id}/intake/payment — แก้ไขหน้า 13
# ---------------------------------------------------------------------------


@router.patch(
    "/cases/{applicant_id}/payment",
    response_model=CasePaymentRead,
    summary="แก้ไขวิธีจ่ายเงิน (case_payment)",
)
async def patch_intake_payment(
    applicant_id: int,
    body: CasePaymentUpsert = Body(...),
    session: AsyncSession = Depends(get_session),
) -> CasePaymentRead:
    handling = await _get_handling_or_404(session, applicant_id)
    payment = await session.scalar(
        select(CasePayment).where(CasePayment.case_handling_id == handling.id)
    )
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="case_payment_not_found"
        )
    return await upsert_intake_payment(applicant_id, body, session)


# ---------------------------------------------------------------------------
# POST /v1/cases/{applicant_id}/intake/ktb — บันทึก KTB Corporate หน้า 20
# ---------------------------------------------------------------------------


@router.post(
    "/cases/{applicant_id}/ktb",
    response_model=CaseKtbCorporateRead,
    status_code=status.HTTP_201_CREATED,
    summary="บันทึก KTB Corporate Online หน้า 20 (twenty_insert) — upsert case_ktb_corporate",
)
async def upsert_intake_ktb(
    applicant_id: int,
    body: CaseKtbCorporateUpsert = Body(...),
    session: AsyncSession = Depends(get_session),
) -> CaseKtbCorporateRead:
    handling = await _get_handling_or_404(session, applicant_id)

    # ตรวจว่าเลือก ktb_corporate จริง ๆ ก่อนบันทึกหน้า 20
    payment = await session.scalar(
        select(CasePayment)
        .where(CasePayment.case_handling_id == handling.id)
        .options(selectinload(CasePayment.payment_method)),
    )
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="case_payment_required_before_ktb",
        )
    if not payment.payment_method.requires_ktb_form:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="payment_method_is_not_ktb",
        )

    if body.payroll_bank_name_id is not None:
        if await session.get(BankName, body.payroll_bank_name_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="payroll_bank_name_not_found",
            )
    if body.other_bank_name_id is not None:
        if await session.get(BankName, body.other_bank_name_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="other_bank_name_not_found"
            )

    ktb = await session.scalar(
        select(CaseKtbCorporate).where(CaseKtbCorporate.case_handling_id == handling.id)
    )

    fields = body.model_dump()
    if ktb is None:
        ktb = CaseKtbCorporate(case_handling_id=handling.id, **fields)
        session.add(ktb)
    else:
        for k, v in fields.items():
            setattr(ktb, k, v)
        ktb.updated_at = datetime.utcnow()

    # อัปเดต intake_completed_at ถ้ายังไม่มี
    if handling.intake_completed_at is None:
        handling.intake_completed_at = datetime.utcnow()

    await session.commit()
    await session.refresh(ktb)
    return CaseKtbCorporateRead.model_validate(ktb)


# ---------------------------------------------------------------------------
# GET /v1/cases/{applicant_id}/intake/ktb
# ---------------------------------------------------------------------------


@router.get(
    "/cases/{applicant_id}/ktb",
    response_model=CaseKtbCorporateRead,
    summary="ดูข้อมูล KTB Corporate (case_ktb_corporate)",
)
async def get_intake_ktb(
    applicant_id: int,
    session: AsyncSession = Depends(get_session),
) -> CaseKtbCorporateRead:
    handling = await _get_handling_or_404(session, applicant_id)
    ktb = await session.scalar(
        select(CaseKtbCorporate).where(CaseKtbCorporate.case_handling_id == handling.id)
    )
    if ktb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="case_ktb_corporate_not_found"
        )
    return CaseKtbCorporateRead.model_validate(ktb)


# ---------------------------------------------------------------------------
# PATCH /v1/cases/{applicant_id}/intake/ktb — แก้ไขหน้า 20
# ---------------------------------------------------------------------------


@router.patch(
    "/cases/{applicant_id}/ktb",
    response_model=CaseKtbCorporateRead,
    summary="แก้ไขข้อมูล KTB Corporate",
)
async def patch_intake_ktb(
    applicant_id: int,
    body: CaseKtbCorporateUpsert = Body(...),
    session: AsyncSession = Depends(get_session),
) -> CaseKtbCorporateRead:
    handling = await _get_handling_or_404(session, applicant_id)
    ktb = await session.scalar(
        select(CaseKtbCorporate).where(CaseKtbCorporate.case_handling_id == handling.id)
    )
    if ktb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="case_ktb_corporate_not_found"
        )
    return await upsert_intake_ktb(applicant_id, body, session)
