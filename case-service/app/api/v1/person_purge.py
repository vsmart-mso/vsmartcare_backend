"""Shared person purge handlers — citizen PDPA + admin ops (CR-05)."""

from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.citizen_security import CitizenClaims, assert_cid_owner, require_citizen
from ...core.database import get_session
from ...core.errors import conflict_from_integrity
from ...core.runtime import require_non_production
from ...models.person import Person
from ...schemas.person import (
    PersonDeleteAllResponse,
    PersonDeleteByCidResponse,
    validate_thai_cid,
)
from ...services.audit_log import write_audit_log
from ...services.person_delete import (
    clear_all_case_payment_person_refs,
    person_delete_load_options,
    purge_person_cases_and_logs,
)
from ..v1.admin import require_admin_token

router = APIRouter(tags=["persons"])


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


async def _delete_person_full(
    session: AsyncSession,
    normalized_cid: str,
) -> PersonDeleteByCidResponse:
    from ...models.applicant import Applicant

    stmt = (
        select(Person)
        .where(Person.cid == normalized_cid)
        .options(*person_delete_load_options())
    )
    person = await session.scalar(stmt)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found")

    purge = await purge_person_cases_and_logs(session, person)
    try:
        remaining = await session.scalar(
            select(func.count()).select_from(Applicant).where(Applicant.persons_id == person.id)
        )
        if remaining:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="delete_blocked_applicants_remain",
            )
        await session.delete(person)
        await session.flush()
    except IntegrityError as exc:
        raise conflict_from_integrity(exc) from exc

    for upload_dir in purge.upload_dirs:
        shutil.rmtree(upload_dir, ignore_errors=True)

    return _purge_to_by_cid_response(
        cid=normalized_cid,
        person=person,
        purge=purge,
        person_deleted=True,
    )


@router.delete(
    "/v1/citizen/person",
    response_model=PersonDeleteByCidResponse,
    summary="PDPA — ลบตัวตนในระบบทั้งหมด (ประชาชน)",
)
async def delete_citizen_person(
    cid: str = Query(..., min_length=13, max_length=13),
    session: AsyncSession = Depends(get_session),
    claims: CitizenClaims = Depends(require_citizen),
) -> PersonDeleteByCidResponse:
    try:
        normalized_cid = validate_thai_cid(cid)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    assert_cid_owner(normalized_cid, claims)
    result = await _delete_person_full(session, normalized_cid)
    await write_audit_log(
        session,
        action="citizen_person_purge",
        actor_type="citizen",
        actor_id=str(claims.person_id),
        target_cid=normalized_cid,
    )
    return result


@router.delete(
    "/v1/admin/persons/by-cid",
    response_model=PersonDeleteByCidResponse,
    summary="Admin — ลบ person ตาม cid",
)
async def admin_delete_person_by_cid(
    cid: str = Query(..., min_length=13, max_length=13),
    session: AsyncSession = Depends(get_session),
    claims: dict = Depends(require_admin_token),
) -> PersonDeleteByCidResponse:
    try:
        normalized_cid = validate_thai_cid(cid)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    result = await _delete_person_full(session, normalized_cid)
    await write_audit_log(
        session,
        action="admin_person_purge",
        actor_type="admin",
        actor_id=str(claims.get("sub") or "unknown"),
        target_cid=normalized_cid,
    )
    return result


async def purge_all_persons_dev(session: AsyncSession) -> PersonDeleteAllResponse:
    """Dev/staging only — used by admin_cli."""
    require_non_production("purge_all_persons")

    stmt = select(Person).options(*person_delete_load_options()).order_by(Person.id)
    persons = list(await session.scalars(stmt))
    cleared_refs = await clear_all_case_payment_person_refs(session)

    deleted_person_ids: list[int] = []
    deleted_applicant_ids: list[int] = []
    deleted_screening_log_count = 0
    deleted_consent_count = 0
    upload_dirs: list = []

    for person in persons:
        purge = await purge_person_cases_and_logs(session, person)
        deleted_person_ids.append(person.id)
        deleted_applicant_ids.extend(purge.deleted_applicant_ids)
        deleted_screening_log_count += len(purge.deleted_screening_log_ids)
        deleted_consent_count += len(purge.deleted_consent_ids)
        upload_dirs.extend(purge.upload_dirs)
        await session.delete(person)
    await session.flush()

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
