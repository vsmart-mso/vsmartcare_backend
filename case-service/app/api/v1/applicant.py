"""เส้นจัดการ applicants แยกจาก flow บันทึกคำร้องหลัก."""

from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.database import get_session
from ...models.person import Person
from ...schemas.applicant import ApplicantDeleteByCidResponse
from ...schemas.person import validate_thai_cid
from ...services.applicant_delete import delete_applicant_cascade
from ...settings import resolved_upload_root

router = APIRouter(prefix="/v1/applicants", tags=["applicants"])


@router.delete(
    "/by-cid",
    response_model=ApplicantDeleteByCidResponse,
    summary="ลบ applicants ตามเลขบัตรประชาชน",
    description=(
        "ค้นหา `persons.cid` แล้วลบ applicant ทุกแถวที่ผูกกับ person คนนั้น "
        "(รวมตารางลูกที่ cascade ตาม applicant_id เช่น `satisfaction_surveys`, "
        "ลบ `screening_logs`, `welfare_request_consents` "
        "และลบโฟลเดอร์ไฟล์หลักฐานของ applicant แต่ละราย)"
    ),
)
async def delete_applicants_by_cid(
    cid: str = Query(..., min_length=13, max_length=13, description="เลขบัตรประชาชน 13 หลัก"),
    session: AsyncSession = Depends(get_session),
) -> ApplicantDeleteByCidResponse:
    try:
        normalized_cid = validate_thai_cid(cid)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    stmt = (
        select(Person)
        .where(Person.cid == normalized_cid)
        .options(
            selectinload(Person.applicants),
            selectinload(Person.screening_logs),
            selectinload(Person.consents),
        )
    )
    result = await session.execute(stmt)
    person = result.scalar_one_or_none()
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found")

    applicants = sorted(person.applicants, key=lambda row: row.id)
    screening_logs = sorted(person.screening_logs, key=lambda row: row.id)
    consents = sorted(person.consents, key=lambda row: row.id)
    if not applicants and not screening_logs and not consents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no_related_data_found_for_cid")

    deleted_applicant_ids = [row.id for row in applicants]
    deleted_screening_log_ids = [row.id for row in screening_logs]
    deleted_consent_ids = [row.id for row in consents]
    upload_dirs = [resolved_upload_root() / str(applicant_id) for applicant_id in deleted_applicant_ids]

    for screening_log in screening_logs:
        await session.delete(screening_log)
    for consent in consents:
        await session.delete(consent)
    try:
        for applicant_id in deleted_applicant_ids:
            await delete_applicant_cascade(session, applicant_id)
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="delete_blocked_by_related_data",
        ) from exc

    for upload_dir in upload_dirs:
        shutil.rmtree(upload_dir, ignore_errors=True)

    return ApplicantDeleteByCidResponse(
        cid=normalized_cid,
        person_id=person.id,
        deleted_applicant_ids=deleted_applicant_ids,
        deleted_count=len(deleted_applicant_ids),
        deleted_screening_log_ids=deleted_screening_log_ids,
        deleted_screening_log_count=len(deleted_screening_log_ids),
        deleted_welfare_request_consent_ids=deleted_consent_ids,
        deleted_welfare_request_consent_count=len(deleted_consent_ids),
    )
