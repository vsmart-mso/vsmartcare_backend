"""เส้นจัดการ applicants แยกจาก flow บันทึกคำร้องหลัก."""

from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_session
from ...models.person import Person
from ...schemas.applicant import ApplicantDeleteByCidResponse
from ...schemas.person import validate_thai_cid
from ...services.person_delete import person_delete_load_options, purge_person_cases_and_logs

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
        .options(*person_delete_load_options())
    )
    person = await session.scalar(stmt)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found")

    if not person.applicants and not person.screening_logs and not person.consents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no_related_data_found_for_cid")

    try:
        purge = await purge_person_cases_and_logs(session, person)
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="delete_blocked_by_related_data",
        ) from exc

    for upload_dir in purge.upload_dirs:
        shutil.rmtree(upload_dir, ignore_errors=True)

    return ApplicantDeleteByCidResponse(
        cid=normalized_cid,
        person_id=person.id,
        deleted_applicant_ids=purge.deleted_applicant_ids,
        deleted_count=len(purge.deleted_applicant_ids),
        deleted_screening_log_ids=purge.deleted_screening_log_ids,
        deleted_screening_log_count=len(purge.deleted_screening_log_ids),
        deleted_welfare_request_consent_ids=purge.deleted_consent_ids,
        deleted_welfare_request_consent_count=len(purge.deleted_consent_ids),
    )
