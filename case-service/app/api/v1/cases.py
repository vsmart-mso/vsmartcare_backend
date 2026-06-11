"""บันทึกคำร้อง (cases) พร้อมตารางย่อย + อัปโหลดหลักฐานเป็นไฟล์รูป (multipart).

`POST /v1/cases` บันทึก applicant / address / dependency / economic /
welfare_request_types / welfare_histories / welfare_request_status แล้ว
อัปโหลดรูปทีหลังด้วย `POST /v1/cases/{applicant_id}/evidences`
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.database import get_session
from ...models.address import Address
from ...models.applicant import Applicant
from ...models.geo import District, SubDistrict, SubDistrictPostcode
from ...models.dependency import DependencyLoad
from ...models.economic import EconomicIncomeSource, EconomicInfo, HouseholdMember
from ...models.intake import CaseHandling
from ...models.lookup import BankAccountType, BankName, CurrentStatus, TypeMoneyCategory
from ...models.person import Person
from ...models.status_log import WelfareRequestStatus
from ...models.review import WelfareReviewComment
from ...models.payment import WelfarePayment
from ...services.payment_round_metrics import applicant_payment_metrics
from ...models.welfare import (
    WelfareEvidence,
    WelfareHistory,
    WelfareHistoryDetail,
    WelfareRequestType,
)
from ...schemas.address import AddressRead
from ...schemas.applicant import ApplicantRead
from ...schemas.case_display import CaseDisplayRead
from ...schemas.case_welfare import (
    WelfareCaseCreate,
    WelfareCaseRead,
    WelfareCaseUpdate,
    WelfareEvidenceUploadRead,
)
from ...schemas.economic import HouseholdMemberRead
from ...schemas.lookup import CurrentStatusRead
from ...api.check_case import check_existing_case_by_cid
from ...services.case_number import allocate_case_number
from ...services.process_sla import process_sla_fields_dict
from ...services.status_email_notification import (
    enqueue_case_submitted_email,
)
from ...services.welfare_evidence import validate_welfare_evidence_upload
from ...schemas.dependency import DependencyLoadRead
from ...schemas.economic import EconomicInfoRead
from ...schemas.status_log import WelfareRequestStatusRead
from ...schemas.welfare import (
    WelfareEvidenceRead,
    WelfareHistoryDetailRead,
    WelfareHistoryRead,
    WelfareRequestTypeRead,
)
from ...settings import resolved_upload_root, settings

ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

router = APIRouter(prefix="/v1/cases", tags=["cases"])


def _dedupe_preserve_order(ids: list[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _applicant_load_options():  # noqa: ANN001
    return [
        selectinload(Applicant.person).selectinload(Person.prefix),
        selectinload(Applicant.type_money_category),
        selectinload(Applicant.requester_relation_type),
        selectinload(Applicant.marital_status),
        selectinload(Applicant.bank_name),
        selectinload(Applicant.addresses).selectinload(Address.address_type),
        selectinload(Applicant.addresses)
        .selectinload(Address.sub_district_postcode)
        .selectinload(SubDistrictPostcode.sub_district)
        .selectinload(SubDistrict.district)
        .selectinload(District.province),
        selectinload(Applicant.addresses)
        .selectinload(Address.sub_district_postcode)
        .selectinload(SubDistrictPostcode.postcode),
        selectinload(Applicant.economic_infos).selectinload(EconomicInfo.income_sources),
        selectinload(Applicant.economic_infos).selectinload(EconomicInfo.housing_type),
        selectinload(Applicant.household_members),
        selectinload(Applicant.dependency_loads),
        selectinload(Applicant.case_handling).selectinload(CaseHandling.regulation_choice),
        selectinload(Applicant.welfare_request_types),
        selectinload(Applicant.welfare_history)
        .selectinload(WelfareHistory.history_details)
        .selectinload(WelfareHistoryDetail.received_welfare_type),
        selectinload(Applicant.welfare_evidences).selectinload(WelfareEvidence.attachment_type),
        selectinload(Applicant.status_logs).selectinload(WelfareRequestStatus.current_status),
        selectinload(Applicant.status_logs)
        .selectinload(WelfareRequestStatus.review_comments)
        .selectinload(WelfareReviewComment.review_field),
    ]


async def _load_applicants_for_display(
    session: AsyncSession,
    persons_id: int,
) -> list[Applicant]:
    stmt = (
        select(Applicant)
        .where(Applicant.persons_id == persons_id)
        .order_by(Applicant.created_at.desc(), Applicant.id.desc())
        .options(selectinload(Applicant.status_logs).selectinload(WelfareRequestStatus.current_status))
    )
    r = await session.execute(stmt)
    return list(r.scalars().all())


async def applicant_to_display_read(applicant: Applicant) -> CaseDisplayRead:
    histories = sorted(applicant.status_logs, key=lambda s: (s.updated_at, s.id), reverse=True)
    latest = histories[0] if histories else None
    status = latest.current_status if latest is not None else None

    return CaseDisplayRead(
        applicant_id=applicant.id,
        case_number=applicant.case_number,
        datetime_create=applicant.created_at,
        is_existing_case=applicant.is_existing_case,
        current_status=CurrentStatusRead.model_validate(status) if status is not None else None,
        description_public=status.description_public if status is not None else None,
        **process_sla_fields_dict(
            applicant.process_started_at,
            applicant.process_sla_days,
            completed_at=applicant.process_completed_at,
            frozen_elapsed=applicant.time_count_process
            if applicant.process_completed_at is not None
            else None,
        ),
    )


async def _load_full_applicant(
    session: AsyncSession,
    applicant_id: int,
) -> Applicant | None:
    stmt = (
        select(Applicant)
        .where(Applicant.id == applicant_id)
        .options(*_applicant_load_options())
    )
    r = await session.execute(stmt)
    return r.scalar_one_or_none()


async def applicant_to_case_read(applicant: Applicant, count_037: int = 0) -> WelfareCaseRead:
    """แปลง ORM Applicant + relationship เป็น WelfareCaseRead (หลัง selectinload แล้ว)"""
    histories = sorted(applicant.status_logs, key=lambda s: (s.updated_at, s.id), reverse=True)

    welfare_history_model = applicant.welfare_history
    welfare_history_read = None
    if welfare_history_model is not None:
        details = sorted(
            welfare_history_model.history_details,
            key=lambda d: (
                d.received_welfare_type_id,
                d.welfare_history_id,
            ),
        )
        welfare_history_read = WelfareHistoryRead(
            applicant_id=welfare_history_model.applicant_id,
            received_count=welfare_history_model.received_count,
            has_received_welfare=welfare_history_model.has_received_welfare,
            total_received_amount=welfare_history_model.total_received_amount,
            history_details=[WelfareHistoryDetailRead.model_validate(d) for d in details],
            created_at=welfare_history_model.created_at,
            updated_at=welfare_history_model.updated_at,
        )

    applicant_read = ApplicantRead.model_validate(
        {
            **ApplicantRead.model_validate(applicant).model_dump(),
            **process_sla_fields_dict(
                applicant.process_started_at,
                applicant.process_sla_days,
                completed_at=applicant.process_completed_at,
                frozen_elapsed=applicant.time_count_process
                if applicant.process_completed_at is not None
                else None,
            ),
        },
    )
    return WelfareCaseRead(
        applicant=applicant_read,
        addresses=[AddressRead.model_validate(a) for a in sorted(applicant.addresses, key=lambda x: x.id)],
        dependency_loads=[
            DependencyLoadRead.model_validate(d)
            for d in sorted(applicant.dependency_loads, key=lambda x: (x.dependency_type_id, x.applicant_id))
        ],
        economic_infos=[
            EconomicInfoRead.model_validate(e) for e in sorted(applicant.economic_infos, key=lambda x: x.id)
        ],
        household_members=[
            HouseholdMemberRead.model_validate(m) for m in sorted(applicant.household_members, key=lambda x: x.seq)
        ],
        welfare_request_types=[
            WelfareRequestTypeRead.model_validate(w) for w in applicant.welfare_request_types
        ],
        welfare_history=welfare_history_read,
        welfare_evidences=[
            WelfareEvidenceRead.model_validate(ev) for ev in sorted(applicant.welfare_evidences, key=lambda x: x.id)
        ],
        welfare_request_status_logs=[WelfareRequestStatusRead.model_validate(s) for s in histories],
        latest_welfare_request_status=WelfareRequestStatusRead.model_validate(histories[0])
        if histories
        else None,
        created_at=applicant.created_at,
        count_037=count_037,
    )


async def _ensure_person_exists(session: AsyncSession, person_id: int) -> None:
    r = await session.execute(select(Person.id).where(Person.id == person_id))
    if r.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found")


async def _ensure_current_status_exists(session: AsyncSession, current_status_id: int) -> None:
    r = await session.execute(select(CurrentStatus.id).where(CurrentStatus.id == current_status_id))
    if r.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="current_status_not_found")


async def _ensure_bank_name_exists(session: AsyncSession, bank_name_id: int) -> None:
    r = await session.execute(select(BankName.id).where(BankName.id == bank_name_id))
    if r.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bank_name_not_found")


async def _ensure_bank_account_type_exists(session: AsyncSession, bank_account_type_id: int) -> None:
    r = await session.execute(
        select(BankAccountType.id).where(BankAccountType.id == bank_account_type_id)
    )
    if r.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="bank_account_type_not_found"
        )


async def _ensure_type_money_category_exists(
    session: AsyncSession,
    type_money_category_id: int,
) -> None:
    r = await session.execute(
        select(TypeMoneyCategory.id).where(TypeMoneyCategory.id == type_money_category_id)
    )
    if r.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="type_money_category_not_found",
        )


@router.post("", response_model=WelfareCaseRead, status_code=status.HTTP_201_CREATED)
async def create_welfare_case(
    body: WelfareCaseCreate,
    session: AsyncSession = Depends(get_session),
) -> WelfareCaseRead:
    await _ensure_person_exists(session, body.applicant.persons_id)
    await _ensure_current_status_exists(session, body.initial_current_status_id)
    if body.applicant.bank_name_id is not None:
        await _ensure_bank_name_exists(session, body.applicant.bank_name_id)
    if body.applicant.bank_account_type_id is not None:
        await _ensure_bank_account_type_exists(session, body.applicant.bank_account_type_id)
    if body.applicant.type_money_category_id is not None:
        await _ensure_type_money_category_exists(session, body.applicant.type_money_category_id)


    req_ids = _dedupe_preserve_order(body.request_type_ids)

    person_cid = await session.scalar(
        select(Person.cid).where(Person.id == body.applicant.persons_id)
    )
    if person_cid is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found")

    # รายใหม่/รายเดิม — เช็ค self + MSO logbook + vsmart_main (ดู app.api.check_case)
    existing_check = await check_existing_case_by_cid(session, person_cid)

    a = body.applicant
    applicant_row = Applicant(
        persons_id=a.persons_id,
        requester_relation_id=a.requester_relation_id,
        marital_status_id=a.marital_status_id,
        mobile_phone=a.mobile_phone,
        home_phone=a.home_phone,
        fax_number=a.fax_number,
        email_address=str(a.email_address) if a.email_address is not None else None,
        problem_details=a.problem_details,
        bank_name_id=a.bank_name_id,
        bank_account_no=a.bank_account_no,
        bank_account_type_id=a.bank_account_type_id,
        bank_branch_name=a.bank_branch_name,
        type_money_category_id=a.type_money_category_id,
        sw_explorer_sdshv=a.sw_explorer_sdshv,
        age=a.age,
        is_existing_case=existing_check.is_existing_case,
        # is_emergency, time_count_process — ใช้ default จากโมเดล ไม่รับจาก client
    )

    session.add(applicant_row)
    try:
        await session.flush()
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    applicant_row.case_number = await allocate_case_number(
        session,
        reference=applicant_row.created_at,
    )
    try:
        await session.flush()
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    aid = applicant_row.id

    for addr in body.addresses:
        session.add(
            Address(
                sub_district_postcode_id=addr.sub_district_postcode_id,
                applicant_id=aid,
                address_type_id=addr.address_type_id,
                alley=addr.alley,
                sub_lane=addr.sub_lane,
                house_name=addr.house_name,
                road=addr.road,
                house_moo=addr.house_moo,
                house_number=addr.house_number,
                mobile_phone=addr.mobile_phone,
                latitude=addr.latitude,
                longitude=addr.longitude,
            )
        )

    for dl in body.dependency_loads:
        session.add(
            DependencyLoad(
                applicant_id=aid,
                dependency_type_id=dl.dependency_type_id,
                dependency_other_text=dl.dependency_other_text,
            )
        )

    hm_count = len(body.household_members)
    for eco in body.economic_infos:
        econ = EconomicInfo(
            applicant_id=aid,
            housing_types_id=eco.housing_types_id,
            housing_types_rent=eco.housing_types_rent,
            occupation=eco.occupation,
            monthly_income=eco.monthly_income,
            household_members=hm_count,  # always override with actual list length
            family_occupation=eco.family_occupation,
        )
        session.add(econ)
        await session.flush()
        for src in eco.income_sources:
            session.add(
                EconomicIncomeSource(
                    economic_id=econ.id,
                    income_source_type_id=src.income_source_type_id,
                    other_details=src.other_details,
                )
            )

    for hm in body.household_members:
        session.add(
            HouseholdMember(
                applicant_id=aid,
                seq=hm.seq,
                national_id=hm.national_id,
                prefix_id=hm.prefix_id,
                prefix_other=hm.prefix_other,
                first_name=hm.first_name,
                last_name=hm.last_name,
                date_of_birth=hm.date_of_birth,
                relation_to_applicant_id=hm.relation_to_applicant_id,
                occupation=hm.occupation,
                monthly_income=hm.monthly_income,
                physical_condition=hm.physical_condition,
                self_care=hm.self_care,
            )
        )

    for rt in req_ids:
        session.add(
            WelfareRequestType(
                applicant_id=aid,
                request_type_id=rt,
                request_other_text=body.request_other_text if rt == 3 else None,
                request_in_kind_text=body.request_in_kind_text if rt == 2 else None,
            )
        )

    if body.welfare_history is not None:
        wh = body.welfare_history
        session.add(
            WelfareHistory(
                applicant_id=aid,
                received_count=wh.received_count,
                has_received_welfare=wh.has_received_welfare,
                total_received_amount=wh.total_received_amount,
            )
        )
        await session.flush()
        for det in wh.history_details:
            session.add(
                WelfareHistoryDetail(
                    welfare_history_id=aid,
                    received_welfare_type_id=det.received_welfare_type_id,
                    received_other=det.received_other,
                )
            )

    status_log = WelfareRequestStatus(
        applicant_id=aid,
        current_status_id=body.initial_current_status_id,
        remarks=None,
        update_by_sdshv=None,
    )
    session.add(status_log)

    try:
        await session.flush()
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    await enqueue_case_submitted_email(
        session,
        applicant_id=aid,
        idempotency_key=f"welfare-case-submitted-{status_log.id}",
        submission_kind="initial",
    )

    reloaded = await _load_full_applicant(session, aid)
    if reloaded is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="reload_failed")

    return await applicant_to_case_read(reloaded)


@router.get("/display", response_model=list[CaseDisplayRead])
async def list_welfare_cases_display(
    persons_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[CaseDisplayRead]:
    await _ensure_person_exists(session, persons_id)
    rows = await _load_applicants_for_display(session, persons_id)
    return [await applicant_to_display_read(row) for row in rows]


@router.patch("/{applicant_id}", response_model=WelfareCaseRead, summary="แก้ไขข้อมูล case ที่มีอยู่แล้ว")
async def update_welfare_case(
    applicant_id: int,
    body: WelfareCaseUpdate,
    session: AsyncSession = Depends(get_session),
) -> WelfareCaseRead:
    """แก้ไข case โดยส่งเฉพาะ section ที่ต้องการเปลี่ยน
    - field = None → ไม่แตะ section นั้น
    - field = list ใหม่ → ลบของเดิมทั้งหมดแล้ว insert ใหม่ (replace)
    """
    # ตรวจว่า case มีอยู่จริง
    applicant_row = await session.get(
        Applicant,
        applicant_id,
        options=[
            selectinload(Applicant.type_money_category),
            selectinload(Applicant.bank_name),
        ],
    )
    if applicant_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_not_found")

    # ── อัปเดต applicant fields (เฉพาะที่ส่งมา) ────────────────────────────────
    if body.applicant is not None:
        a = body.applicant
        if a.requester_relation_id is not None:
            applicant_row.requester_relation_id = a.requester_relation_id
        if a.marital_status_id is not None:
            applicant_row.marital_status_id = a.marital_status_id
        if a.mobile_phone is not None:
            applicant_row.mobile_phone = a.mobile_phone
        if a.home_phone is not None:
            applicant_row.home_phone = a.home_phone
        if a.fax_number is not None:
            applicant_row.fax_number = a.fax_number
        if a.email_address is not None:
            applicant_row.email_address = str(a.email_address)
        if a.problem_details is not None:
            applicant_row.problem_details = a.problem_details
        if a.bank_name_id is not None:
            await _ensure_bank_name_exists(session, a.bank_name_id)
            applicant_row.bank_name_id = a.bank_name_id
        if a.bank_account_no is not None:
            applicant_row.bank_account_no = a.bank_account_no
        if a.bank_account_type_id is not None:
            await _ensure_bank_account_type_exists(session, a.bank_account_type_id)
            applicant_row.bank_account_type_id = a.bank_account_type_id
        if a.bank_branch_name is not None:
            applicant_row.bank_branch_name = a.bank_branch_name
        if a.age is not None:
            applicant_row.age = a.age
        if a.reset_processing_state:
            applicant_row.process_started_at     = None
            applicant_row.process_sla_days       = None
            applicant_row.process_completed_at   = None
            applicant_row.time_count_process     = None
            applicant_row.type_money_category_id = None

    # ── Replace addresses ────────────────────────────────────────────────────────
    if body.addresses is not None:
        await session.execute(delete(Address).where(Address.applicant_id == applicant_id))
        for addr in body.addresses:
            session.add(Address(
                applicant_id=applicant_id,
                sub_district_postcode_id=addr.sub_district_postcode_id,
                address_type_id=addr.address_type_id,
                alley=addr.alley,
                sub_lane=addr.sub_lane,
                house_name=addr.house_name,
                road=addr.road,
                house_moo=addr.house_moo,
                house_number=addr.house_number,
                mobile_phone=addr.mobile_phone,
                latitude=addr.latitude,
                longitude=addr.longitude,
            ))

    # ── Replace dependency_loads ─────────────────────────────────────────────────
    if body.dependency_loads is not None:
        await session.execute(delete(DependencyLoad).where(DependencyLoad.applicant_id == applicant_id))
        for dl in body.dependency_loads:
            session.add(DependencyLoad(
                applicant_id=applicant_id,
                dependency_type_id=dl.dependency_type_id,
                dependency_other_text=dl.dependency_other_text,
            ))

    # ── Replace economic_infos ───────────────────────────────────────────────────
    hm_count_for_update = len(body.household_members) if body.household_members is not None else None
    if body.economic_infos is not None:
        # bulk DELETE ไม่ trigger ORM cascade ต้องลบ EconomicIncomeSource ก่อน
        eco_id_subq = select(EconomicInfo.id).where(EconomicInfo.applicant_id == applicant_id)
        await session.execute(delete(EconomicIncomeSource).where(EconomicIncomeSource.economic_id.in_(eco_id_subq)))
        await session.execute(delete(EconomicInfo).where(EconomicInfo.applicant_id == applicant_id))
        await session.flush()
        for eco in body.economic_infos:
            econ = EconomicInfo(
                applicant_id=applicant_id,
                housing_types_id=eco.housing_types_id,
                housing_types_rent=eco.housing_types_rent,
                occupation=eco.occupation,
                monthly_income=eco.monthly_income,
                household_members=hm_count_for_update if hm_count_for_update is not None else eco.household_members,
                family_occupation=eco.family_occupation,
            )
            session.add(econ)
            await session.flush()
            for src in eco.income_sources:
                session.add(EconomicIncomeSource(
                    economic_id=econ.id,
                    income_source_type_id=src.income_source_type_id,
                    other_details=src.other_details,
                ))

    # ── Replace household_members ────────────────────────────────────────────────
    if body.household_members is not None:
        await session.execute(delete(HouseholdMember).where(HouseholdMember.applicant_id == applicant_id))
        for hm in body.household_members:
            session.add(HouseholdMember(
                applicant_id=applicant_id,
                seq=hm.seq,
                national_id=hm.national_id,
                prefix_id=hm.prefix_id,
                prefix_other=hm.prefix_other,
                first_name=hm.first_name,
                last_name=hm.last_name,
                date_of_birth=hm.date_of_birth,
                relation_to_applicant_id=hm.relation_to_applicant_id,
                occupation=hm.occupation,
                monthly_income=hm.monthly_income,
                physical_condition=hm.physical_condition,
                self_care=hm.self_care,
            ))
        # sync count into economic_infos when economic_infos was not replaced this request
        if body.economic_infos is None:
            from sqlalchemy import update as sa_update
            await session.execute(
                sa_update(EconomicInfo)
                .where(EconomicInfo.applicant_id == applicant_id)
                .values(household_members=len(body.household_members))
            )

    # ── Replace request_type_ids ─────────────────────────────────────────────────
    if body.request_type_ids is not None:
        await session.execute(delete(WelfareRequestType).where(WelfareRequestType.applicant_id == applicant_id))
        for rt in _dedupe_preserve_order(body.request_type_ids):
            session.add(WelfareRequestType(
                applicant_id=applicant_id,
                request_type_id=rt,
                request_other_text=body.request_other_text if rt == 3 else None,
                request_in_kind_text=body.request_in_kind_text if rt == 2 else None,
            ))

    # ── Replace welfare_history (1:1 — upsert by applicant_id) ──────────────────
    if body.welfare_history is not None:
        existing_wh = await session.get(WelfareHistory, applicant_id)
        wh = body.welfare_history
        if existing_wh is not None:
            existing_wh.received_count = wh.received_count
            existing_wh.has_received_welfare = wh.has_received_welfare
            existing_wh.total_received_amount = wh.total_received_amount
            await session.flush()
            await session.execute(
                delete(WelfareHistoryDetail).where(WelfareHistoryDetail.welfare_history_id == applicant_id)
            )
        else:
            new_wh = WelfareHistory(
                applicant_id=applicant_id,
                received_count=wh.received_count,
                has_received_welfare=wh.has_received_welfare,
                total_received_amount=wh.total_received_amount,
            )
            session.add(new_wh)
            await session.flush()
        for det in wh.history_details:
            session.add(WelfareHistoryDetail(
                welfare_history_id=applicant_id,
                received_welfare_type_id=det.received_welfare_type_id,
                received_other=det.received_other,
            ))

    try:
        await session.flush()
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    reloaded = await _load_full_applicant(session, applicant_id)
    if reloaded is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="reload_failed")
    return await applicant_to_case_read(reloaded)


@router.get("/{applicant_id}", response_model=WelfareCaseRead)
async def get_welfare_case(
    applicant_id: int,
    session: AsyncSession = Depends(get_session),
) -> WelfareCaseRead:
    row = await _load_full_applicant(session, applicant_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_not_found")

    payments_result = await session.execute(
        select(WelfarePayment)
        .where(WelfarePayment.applicant_id == applicant_id)
        .order_by(WelfarePayment.id.asc()),
    )
    metrics = applicant_payment_metrics(list(payments_result.scalars().all()))
    count_037 = int(metrics["count_037"])

    return await applicant_to_case_read(row, count_037=count_037)


@router.get(
    "/{applicant_id}/evidences/{evidence_id}/file",
    summary="ดาวน์โหลดไฟล์หลักฐาน (รูป)",
    response_class=FileResponse,
)
async def get_welfare_evidence_file(
    applicant_id: int,
    evidence_id: int,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    ev = await session.get(WelfareEvidence, evidence_id)
    if ev is None or ev.applicant_id != applicant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence_not_found")

    root = resolved_upload_root().resolve()
    path = (root / ev.file_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="evidence_file_invalid_path",
        ) from e
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence_file_missing")

    suffix = path.suffix.lower()
    media = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "application/octet-stream")
    download_name = ev.file_original_name or ev.file_stored_name or path.name
    return FileResponse(path, media_type=media, filename=download_name)


@router.delete(
    "/{applicant_id}/evidences/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="ลบหลักฐาน (รูป) — ลบทั้ง DB record และไฟล์บน disk",
)
async def delete_welfare_evidence(
    applicant_id: int,
    evidence_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    ev = await session.get(WelfareEvidence, evidence_id)
    if ev is None or ev.applicant_id != applicant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence_not_found")

    # ลบไฟล์จาก disk ก่อน (ถ้าไม่มีก็ข้ามได้)
    root = resolved_upload_root().resolve()
    path = (root / ev.file_path).resolve()
    try:
        path.relative_to(root)
        path.unlink(missing_ok=True)
    except ValueError:
        pass  # path traversal guard — ข้ามการลบไฟล์ แต่ยังลบ DB record

    await session.delete(ev)


@router.patch(
    "/{applicant_id}/evidences/{evidence_id}",
    summary="แก้ไขชื่อเอกสาร (สำหรับ attachment_type_id = อื่นๆ)",
)
async def update_welfare_evidence_name(
    applicant_id: int,
    evidence_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
) -> dict:
    ev = await session.get(WelfareEvidence, evidence_id)
    if ev is None or ev.applicant_id != applicant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence_not_found")
    if "file_other_type_name" in body:
        ev.file_other_type_name = body["file_other_type_name"]
    await session.commit()
    await session.refresh(ev)
    return {"id": ev.id, "file_other_type_name": ev.file_other_type_name}


@router.post(
    "/{applicant_id}/evidences",
    response_model=WelfareEvidenceUploadRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_welfare_evidence_image(
    applicant_id: int,
    attachment_type_id: int = Form(..., ge=1),
    file_other_type_name: str | None = Form(None),
    file: UploadFile = File(..., description="ไฟล์รูป (jpeg/png/webp/gif) — ไม่ใช้ Base64"),
    session: AsyncSession = Depends(get_session),
) -> WelfareEvidenceUploadRead:
    row_check = await session.execute(select(Applicant.id).where(Applicant.id == applicant_id))
    if row_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_not_found")

    normalized_other_name = await validate_welfare_evidence_upload(
        session,
        attachment_type_id,
        file_other_type_name,
    )

    raw_content_type = (file.content_type or "").split(";")[0].strip().lower()
    if raw_content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="unsupported_media_type_expect_image",
        )

    ext = ALLOWED_IMAGE_TYPES[raw_content_type]
    blob = await file.read()
    if len(blob) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file_too_large")

    base = resolved_upload_root()
    dest_dir = (base / str(applicant_id)).resolve()
    try:
        dest_dir.relative_to(base.resolve())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="upload_path_invalid") from e

    dest_dir.mkdir(parents=True, exist_ok=True)

    stored = f"{uuid.uuid4().hex}{ext}"
    full_path = dest_dir / stored
    full_path.write_bytes(blob)

    relative_for_db = f"{applicant_id}/{stored}"

    evidence = WelfareEvidence(
        attachment_type_id=attachment_type_id,
        applicant_id=applicant_id,
        file_path=relative_for_db,
        file_original_name=file.filename,
        file_stored_name=stored,
        file_size=len(blob),
        file_other_type_name=normalized_other_name,
    )
    session.add(evidence)
    try:
        await session.flush()
    except IntegrityError as e:
        if full_path.is_file():
            full_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    await session.refresh(evidence)
    return WelfareEvidenceUploadRead(evidence=WelfareEvidenceRead.model_validate(evidence))


@router.put(
    "/{applicant_id}/evidences/{evidence_id}",
    response_model=WelfareEvidenceUploadRead,
    summary="แก้ไขรูปหลักฐาน",
)
async def update_welfare_evidence_image(
    applicant_id: int,
    evidence_id: int,
    attachment_type_id: int = Form(..., ge=1),
    file_other_type_name: str | None = Form(None),
    file: UploadFile = File(..., description="ไฟล์รูปใหม่ (jpeg/png/webp/gif)"),
    session: AsyncSession = Depends(get_session),
) -> WelfareEvidenceUploadRead:
    ev = await session.get(WelfareEvidence, evidence_id)
    if ev is None or ev.applicant_id != applicant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence_not_found")

    normalized_other_name = await validate_welfare_evidence_upload(
        session,
        attachment_type_id,
        file_other_type_name,
    )

    raw_content_type = (file.content_type or "").split(";")[0].strip().lower()
    if raw_content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="unsupported_media_type_expect_image",
        )

    blob = await file.read()
    if len(blob) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file_too_large")

    ext = ALLOWED_IMAGE_TYPES[raw_content_type]
    base = resolved_upload_root()
    dest_dir = (base / str(applicant_id)).resolve()
    try:
        dest_dir.relative_to(base.resolve())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="upload_path_invalid") from e

    dest_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    new_full_path = dest_dir / stored
    new_full_path.write_bytes(blob)

    old_file = (base / ev.file_path).resolve()
    old_file.unlink(missing_ok=True)

    ev.attachment_type_id = attachment_type_id
    ev.file_path = f"{applicant_id}/{stored}"
    ev.file_original_name = file.filename
    ev.file_stored_name = stored
    ev.file_size = len(blob)
    ev.file_other_type_name = normalized_other_name

    await session.flush()
    await session.refresh(ev)
    return WelfareEvidenceUploadRead(evidence=WelfareEvidenceRead.model_validate(ev))


@router.delete(
    "/{applicant_id}/evidences/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="ลบรูปหลักฐาน",
)
async def delete_welfare_evidence_image(
    applicant_id: int,
    evidence_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    ev = await session.get(WelfareEvidence, evidence_id)
    if ev is None or ev.applicant_id != applicant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence_not_found")

    file_path = (resolved_upload_root() / ev.file_path).resolve()
    await session.delete(ev)
    await session.flush()
    file_path.unlink(missing_ok=True)
