"""เส้น reset / ลบ persons — อยู่ใกล้ applicants/by-cid."""

from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_session
from ...models.person import Person
from ...schemas.person import (
    PersonDeleteAllResponse,
    PersonDeleteByCidResponse,
    validate_thai_cid,
)
from ...services.person_delete import (
    clear_all_case_payment_person_refs,
    person_delete_load_options,
    purge_person_cases_and_logs,
)

router = APIRouter(prefix="/v1/persons", tags=["persons"])


def _purge_to_by_cid_response(
    *,
    cid: str,
    person: Person,
    purge,
    person_deleted: bool,
) -> PersonDeleteByCidResponse:
    return PersonDeleteByCidResponse(
        cid=cid,
        person_id=person.id,
        person_deleted=person_deleted,
        deleted_applicant_ids=purge.deleted_applicant_ids,
        deleted_count=len(purge.deleted_applicant_ids),
        deleted_screening_log_ids=purge.deleted_screening_log_ids,
        deleted_screening_log_count=len(purge.deleted_screening_log_ids),
        deleted_welfare_request_consent_ids=purge.deleted_consent_ids,
        deleted_welfare_request_consent_count=len(purge.deleted_consent_ids),
        cleared_case_payment_refs=purge.cleared_case_payment_refs,
    )


@router.delete(
    "/by-cid",
    response_model=PersonDeleteByCidResponse,
    summary="ลบ person ตามเลขบัตรประชาชน (reset บุคคลและเคส)",
    description=(
        "ค้นหา `persons.cid` แล้วลบ applicants ทุกรายการ ข้อมูลตารางย่อย "
        "`screening_logs`, `welfare_request_consents` และแถว `persons` "
        "(เคลียร์ `case_payment.agent_person_id` / `payee_person_id` ที่อ้างคนนี้ก่อน)"
    ),
)
async def delete_person_by_cid(
    cid: str = Query(..., min_length=13, max_length=13, description="เลขบัตรประชาชน 13 หลัก"),
    session: AsyncSession = Depends(get_session),
) -> PersonDeleteByCidResponse:
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

    try:
        purge = await purge_person_cases_and_logs(session, person)
        await session.delete(person)
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="delete_blocked_by_related_data",
        ) from exc

    for upload_dir in purge.upload_dirs:
        shutil.rmtree(upload_dir, ignore_errors=True)

    return _purge_to_by_cid_response(
        cid=normalized_cid,
        person=person,
        purge=purge,
        person_deleted=True,
    )


@router.delete(
    "/all",
    response_model=PersonDeleteAllResponse,
    summary="ลบ persons ทั้งหมด (reset ข้อมูลบุคคลและเคสทั้งระบบ)",
    description=(
        "ลบทุกแถวใน `persons` พร้อม applicants และข้อมูลที่ผูกกับแต่ละ person "
        "(เคลียร์ `case_payment` person refs ทั้งหมดก่อนลบ)"
    ),
)
async def delete_all_persons(
    session: AsyncSession = Depends(get_session),
) -> PersonDeleteAllResponse:
    stmt = select(Person).options(*person_delete_load_options()).order_by(Person.id)
    persons = list(await session.scalars(stmt))

    cleared_refs = await clear_all_case_payment_person_refs(session)

    deleted_person_ids: list[int] = []
    deleted_applicant_ids: list[int] = []
    deleted_screening_log_count = 0
    deleted_consent_count = 0
    upload_dirs: list = []

    try:
        for person in persons:
            purge = await purge_person_cases_and_logs(session, person)
            deleted_person_ids.append(person.id)
            deleted_applicant_ids.extend(purge.deleted_applicant_ids)
            deleted_screening_log_count += len(purge.deleted_screening_log_ids)
            deleted_consent_count += len(purge.deleted_consent_ids)
            upload_dirs.extend(purge.upload_dirs)
            await session.delete(person)
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="delete_blocked_by_related_data",
        ) from exc

    for upload_dir in upload_dirs:
        shutil.rmtree(upload_dir, ignore_errors=True)

    return PersonDeleteAllResponse(
        deleted_person_count=len(deleted_person_ids),
        deleted_person_ids=deleted_person_ids,
        deleted_applicant_count=len(deleted_applicant_ids),
        deleted_applicant_ids=deleted_applicant_ids,
        deleted_screening_log_count=deleted_screening_log_count,
        deleted_welfare_request_consent_count=deleted_consent_count,
        cleared_case_payment_refs=cleared_refs,
    )
