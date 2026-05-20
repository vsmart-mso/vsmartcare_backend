"""ลบ person พร้อม applicants / screening / consent — reset ข้อมูลบุคคลและเคส."""

from __future__ import annotations

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.intake import CasePayment
from ..models.person import Person
from .applicant_delete import delete_applicant_cascade


def person_delete_load_options():  # noqa: ANN201
    return [
        selectinload(Person.applicants),
        selectinload(Person.screening_logs),
        selectinload(Person.consents),
    ]


async def clear_case_payment_person_refs(session: AsyncSession, person_id: int) -> int:
    """เคลียร์ FK จาก case_payment ที่อ้าง person คนอื่น (agent/payee) ก่อนลบ persons."""
    result = await session.execute(
        update(CasePayment)
        .where(
            or_(
                CasePayment.agent_person_id == person_id,
                CasePayment.payee_person_id == person_id,
            )
        )
        .values(
            agent_person_id=None,
            payee_person_id=None,
        )
    )
    return result.rowcount or 0


async def clear_all_case_payment_person_refs(session: AsyncSession) -> int:
    result = await session.execute(
        update(CasePayment)
        .where(
            or_(
                CasePayment.agent_person_id.isnot(None),
                CasePayment.payee_person_id.isnot(None),
            )
        )
        .values(agent_person_id=None, payee_person_id=None)
    )
    return result.rowcount or 0


class PersonPurgeResult:
    __slots__ = (
        "deleted_applicant_ids",
        "deleted_screening_log_ids",
        "deleted_consent_ids",
        "upload_dirs",
        "cleared_case_payment_refs",
    )

    def __init__(
        self,
        *,
        deleted_applicant_ids: list[int],
        deleted_screening_log_ids: list[int],
        deleted_consent_ids: list[int],
        upload_dirs: list,
        cleared_case_payment_refs: int,
    ) -> None:
        self.deleted_applicant_ids = deleted_applicant_ids
        self.deleted_screening_log_ids = deleted_screening_log_ids
        self.deleted_consent_ids = deleted_consent_ids
        self.upload_dirs = upload_dirs
        self.cleared_case_payment_refs = cleared_case_payment_refs


async def purge_person_cases_and_logs(session: AsyncSession, person: Person) -> PersonPurgeResult:
    """ลบ applicants (cascade), screening_logs, welfare_request_consents ของ person — ยังไม่ลบแถว persons."""
    applicants = sorted(person.applicants, key=lambda row: row.id)
    screening_logs = sorted(person.screening_logs, key=lambda row: row.id)
    consents = sorted(person.consents, key=lambda row: row.id)

    cleared_refs = await clear_case_payment_person_refs(session, person.id)

    deleted_applicant_ids = [row.id for row in applicants]
    deleted_screening_log_ids = [row.id for row in screening_logs]
    deleted_consent_ids = [row.id for row in consents]

    for screening_log in screening_logs:
        await session.delete(screening_log)
    for consent in consents:
        await session.delete(consent)
    for applicant_id in deleted_applicant_ids:
        await delete_applicant_cascade(session, applicant_id)

    from ..settings import resolved_upload_root

    upload_dirs = [resolved_upload_root() / str(applicant_id) for applicant_id in deleted_applicant_ids]

    return PersonPurgeResult(
        deleted_applicant_ids=deleted_applicant_ids,
        deleted_screening_log_ids=deleted_screening_log_ids,
        deleted_consent_ids=deleted_consent_ids,
        upload_dirs=upload_dirs,
        cleared_case_payment_refs=cleared_refs,
    )
