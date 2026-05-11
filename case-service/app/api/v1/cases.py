"""บันทึกคำร้อง (cases) พร้อมตารางย่อย + อัปโหลดหลักฐานเป็นไฟล์รูป (multipart).

`POST /v1/cases` บันทึก applicant / address / dependency / economic /
welfare_request_types / welfare_histories / welfare_request_status แล้ว
อัปโหลดรูปทีหลังด้วย `POST /v1/cases/{applicant_id}/evidences`
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.database import get_session
from ...models.address import Address
from ...models.applicant import Applicant
from ...models.dependency import DependencyLoad
from ...models.economic import EconomicIncomeSource, EconomicInfo
from ...models.lookup import CurrentStatus
from ...models.person import Person
from ...models.status_log import WelfareRequestStatus
from ...models.welfare import (
    WelfareEvidence,
    WelfareHistory,
    WelfareHistoryDetail,
    WelfareRequestType,
)
from ...schemas.address import AddressRead
from ...schemas.applicant import ApplicantRead
from ...schemas.case_welfare import (
    WelfareCaseCreate,
    WelfareCaseRead,
    WelfareEvidenceUploadRead,
)
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
        selectinload(Applicant.person),
        selectinload(Applicant.requester_relation_type),
        selectinload(Applicant.marital_status),
        selectinload(Applicant.addresses).selectinload(Address.address_type),
        selectinload(Applicant.addresses).selectinload(Address.sub_district_postcode),
        selectinload(Applicant.economic_infos).selectinload(EconomicInfo.income_sources),
        selectinload(Applicant.economic_infos).selectinload(EconomicInfo.housing_type),
        selectinload(Applicant.dependency_loads),
        selectinload(Applicant.welfare_request_types),
        selectinload(Applicant.welfare_history).selectinload(WelfareHistory.history_details),
        selectinload(Applicant.welfare_evidences),
        selectinload(Applicant.status_logs).selectinload(WelfareRequestStatus.current_status),
    ]


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


async def applicant_to_case_read(applicant: Applicant) -> WelfareCaseRead:
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

    return WelfareCaseRead(
        applicant=ApplicantRead.model_validate(applicant),
        addresses=[AddressRead.model_validate(a) for a in sorted(applicant.addresses, key=lambda x: x.id)],
        dependency_loads=[
            DependencyLoadRead.model_validate(d)
            for d in sorted(applicant.dependency_loads, key=lambda x: (x.dependency_type_id, x.applicant_id))
        ],
        economic_infos=[
            EconomicInfoRead.model_validate(e) for e in sorted(applicant.economic_infos, key=lambda x: x.id)
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
    )


async def _ensure_person_exists(session: AsyncSession, person_id: int) -> None:
    r = await session.execute(select(Person.id).where(Person.id == person_id))
    if r.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found")


async def _ensure_current_status_exists(session: AsyncSession, current_status_id: int) -> None:
    r = await session.execute(select(CurrentStatus.id).where(CurrentStatus.id == current_status_id))
    if r.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="current_status_not_found")


@router.post("", response_model=WelfareCaseRead, status_code=status.HTTP_201_CREATED)
async def create_welfare_case(
    body: WelfareCaseCreate,
    session: AsyncSession = Depends(get_session),
) -> WelfareCaseRead:
    await _ensure_person_exists(session, body.applicant.persons_id)
    await _ensure_current_status_exists(session, body.initial_current_status_id)

    req_ids = _dedupe_preserve_order(body.request_type_ids)

    a = body.applicant
    applicant_row = Applicant(
        persons_id=a.persons_id,
        case_number=a.case_number,
        requester_relation_id=a.requester_relation_id,
        marital_status_id=a.marital_status_id,
        mobile_phone=a.mobile_phone,
        home_phone=a.home_phone,
        fax_number=a.fax_number,
        email_address=str(a.email_address) if a.email_address is not None else None,
        problem_details=a.problem_details,
        bank_account_name=a.bank_account_name,
        bank_account_no=a.bank_account_no,
        age=a.age,
        # is_existing_case, is_emergency, time_count_process — ใช้ default จากโมเดล ไม่รับจาก client
    )

    session.add(applicant_row)
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

    for eco in body.economic_infos:
        econ = EconomicInfo(
            applicant_id=aid,
            housing_types_id=eco.housing_types_id,
            occupation=eco.occupation,
            monthly_income=eco.monthly_income,
            household_members=eco.household_members,
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

    for rt in req_ids:
        session.add(
            WelfareRequestType(
                applicant_id=aid,
                request_type_id=rt,
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

    session.add(
        WelfareRequestStatus(
            applicant_id=aid,
            current_status_id=body.initial_current_status_id,
            remarks=None,
            update_by_sdshv=None,
        )
    )

    try:
        await session.flush()
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    reloaded = await _load_full_applicant(session, aid)
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
    return await applicant_to_case_read(row)


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
        file_other_type_name=file_other_type_name,
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
