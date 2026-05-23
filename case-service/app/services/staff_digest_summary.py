"""สรุปจำนวนคำร้องตาม bucket สำหรับ staff digest (จังหวัดเดียว)."""

from __future__ import annotations

from sqlalchemy import and_, case as sql_case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants.staff_digest import (
    CURRENT_STATUS_PENDING_INTAKE,
    CURRENT_STATUS_WITHDRAWING_IDS,
)
from ..models.address import Address
from ..models.applicant import Applicant
from ..models.geo import District, Postcode, Province, SubDistrict, SubDistrictPostcode
from ..models.payment import ApproveCase
from ..models.person import Person
from ..models.status_log import WelfareRequestStatus
from ..schemas.case_for_staff import CaseForStaffStatusSummaryResponse


def _latest_welfare_request_status_subquery():
    return (
        select(
            WelfareRequestStatus.applicant_id.label("applicant_id"),
            WelfareRequestStatus.current_status_id.label("current_status_id"),
            func.row_number()
            .over(
                partition_by=WelfareRequestStatus.applicant_id,
                order_by=[WelfareRequestStatus.updated_at.desc(), WelfareRequestStatus.id.desc()],
            )
            .label("rn"),
        )
        .subquery()
    )


def _applicant_is_approved_exists():
    """มีแถว approve_case ที่ approve_status = true สำหรับ applicant นี้หรือไม่."""
    return (
        select(ApproveCase.id)
        .where(
            ApproveCase.applicant_id == Applicant.id,
            ApproveCase.approve_status.is_(True),
        )
        .exists()
    )


def _province_applicants_subquery(province_id: int):
    primary_address_sq = (
        select(
            Address.applicant_id.label("applicant_id"),
            Address.sub_district_postcode_id.label("sub_district_postcode_id"),
            func.row_number()
            .over(
                partition_by=Address.applicant_id,
                order_by=[Address.id.asc()],
            )
            .label("rn"),
        )
        .subquery()
    )

    location_subdistrict_postcode_id = func.coalesce(
        primary_address_sq.c.sub_district_postcode_id,
        Person.sub_district_postcode_id,
    )

    latest_status_sq = _latest_welfare_request_status_subquery()
    is_approved = _applicant_is_approved_exists()

    return (
        select(
            Applicant.id.label("applicant_id"),
            latest_status_sq.c.current_status_id.label("current_status_id"),
            is_approved.label("is_approved"),
            Applicant.is_emergency.label("is_emergency"),
        )
        .select_from(Applicant)
        .join(Person, Person.id == Applicant.persons_id)
        .outerjoin(
            primary_address_sq,
            and_(
                primary_address_sq.c.applicant_id == Applicant.id,
                primary_address_sq.c.rn == 1,
            ),
        )
        .join(
            SubDistrictPostcode,
            SubDistrictPostcode.id == location_subdistrict_postcode_id,
        )
        .join(Postcode, Postcode.id == SubDistrictPostcode.postcode_id)
        .join(SubDistrict, SubDistrict.id == SubDistrictPostcode.sub_district_id)
        .join(District, District.id == SubDistrict.district_id)
        .join(Province, Province.id == District.province_id)
        .outerjoin(
            latest_status_sq,
            and_(
                latest_status_sq.c.applicant_id == Applicant.id,
                latest_status_sq.c.rn == 1,
            ),
        )
        .where(Province.id == province_id)
        .subquery()
    )


def _is_withdrawing_status(current_status_id_column):
    return current_status_id_column.in_(CURRENT_STATUS_WITHDRAWING_IDS)


async def fetch_staff_digest_summary(
    session: AsyncSession,
    province_id: int,
) -> CaseForStaffStatusSummaryResponse | None:
    """คืน None เมื่อไม่พบจังหวัด."""
    province = await session.scalar(select(Province).where(Province.id == province_id))
    if province is None:
        return None

    applicants_sq = _province_applicants_subquery(province_id)
    is_withdrawing = _is_withdrawing_status(applicants_sq.c.current_status_id)
    is_emergency = applicants_sq.c.is_emergency.is_(True)

    agg_stmt = select(
        func.count().label("total_applicants"),
        func.coalesce(
            func.sum(
                sql_case(
                    (applicants_sq.c.current_status_id == CURRENT_STATUS_PENDING_INTAKE, 1),
                    else_=0,
                )
            ),
            0,
        ).label("social_worker_pending"),
        func.coalesce(
            func.sum(sql_case((is_withdrawing, 1), else_=0)),
            0,
        ).label("withdrawing_in_progress"),
        func.coalesce(
            func.sum(
                sql_case(
                    (
                        and_(
                            is_withdrawing,
                            applicants_sq.c.is_approved.is_(False),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("pmj_pending_approve"),
        func.coalesce(
            func.sum(
                sql_case(
                    (
                        and_(
                            is_withdrawing,
                            applicants_sq.c.is_approved.is_(True),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("finance_pending"),
        func.coalesce(
            func.sum(
                sql_case(
                    (
                        and_(
                            applicants_sq.c.current_status_id == CURRENT_STATUS_PENDING_INTAKE,
                            is_emergency,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("social_worker_emergency"),
        func.coalesce(
            func.sum(
                sql_case(
                    (
                        and_(
                            is_withdrawing,
                            applicants_sq.c.is_approved.is_(False),
                            is_emergency,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("pmj_emergency"),
        func.coalesce(
            func.sum(
                sql_case(
                    (
                        and_(
                            is_withdrawing,
                            applicants_sq.c.is_approved.is_(True),
                            is_emergency,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("finance_emergency"),
    ).select_from(applicants_sq)

    row = (await session.execute(agg_stmt)).mappings().one()

    return CaseForStaffStatusSummaryResponse(
        province_id=province.id,
        province_name=province.name,
        total_applicants=int(row["total_applicants"] or 0),
        social_worker_pending=int(row["social_worker_pending"] or 0),
        withdrawing_in_progress=int(row["withdrawing_in_progress"] or 0),
        pmj_pending_approve=int(row["pmj_pending_approve"] or 0),
        finance_pending=int(row["finance_pending"] or 0),
        social_worker_emergency=int(row["social_worker_emergency"] or 0),
        pmj_emergency=int(row["pmj_emergency"] or 0),
        finance_emergency=int(row["finance_emergency"] or 0),
    )


async def resolve_applicant_province_id(
    session: AsyncSession,
    applicant_id: int,
) -> int | None:
    """จังหวัดจากที่อยู่หลักของ applicant (fallback ที่อยู่บุคคล) — logic เดียวกับ staff digest."""
    primary_address_sq = (
        select(
            Address.applicant_id.label("applicant_id"),
            Address.sub_district_postcode_id.label("sub_district_postcode_id"),
            func.row_number()
            .over(
                partition_by=Address.applicant_id,
                order_by=[Address.id.asc()],
            )
            .label("rn"),
        )
        .subquery()
    )

    location_subdistrict_postcode_id = func.coalesce(
        primary_address_sq.c.sub_district_postcode_id,
        Person.sub_district_postcode_id,
    )

    stmt = (
        select(Province.id)
        .select_from(Applicant)
        .join(Person, Person.id == Applicant.persons_id)
        .outerjoin(
            primary_address_sq,
            and_(
                primary_address_sq.c.applicant_id == Applicant.id,
                primary_address_sq.c.rn == 1,
            ),
        )
        .join(
            SubDistrictPostcode,
            SubDistrictPostcode.id == location_subdistrict_postcode_id,
        )
        .join(Postcode, Postcode.id == SubDistrictPostcode.postcode_id)
        .join(SubDistrict, SubDistrict.id == SubDistrictPostcode.sub_district_id)
        .join(District, District.id == SubDistrict.district_id)
        .join(Province, Province.id == District.province_id)
        .where(Applicant.id == applicant_id)
    )
    return await session.scalar(stmt)


async def fetch_province_totals_for_applicant(
    session: AsyncSession,
    applicant_id: int,
) -> dict[str, object]:
    """ชื่อจังหวัดและจำนวนคำร้องทั้งหมดในจังหวัด — สำหรับ payload อีเมล."""
    province_id = await resolve_applicant_province_id(session, applicant_id)
    if province_id is None:
        return {}

    summary = await fetch_staff_digest_summary(session, province_id)
    if summary is None:
        return {}

    return {
        "province_name": summary.province_name,
        "total_applicants": summary.total_applicants,
    }
