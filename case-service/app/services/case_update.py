"""Shared case update logic — used by citizen PATCH and staff case-sections PATCH."""

from __future__ import annotations

from sqlalchemy import delete, select, update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from ..models.address import Address
from ..models.applicant import Applicant
from ..models.dependency import DependencyLoad
from ..models.economic import EconomicIncomeSource, EconomicInfo, HouseholdMember
from ..models.lookup import BankAccountType, BankName
from ..models.welfare import (
    WelfareHistory,
    WelfareHistoryDetail,
    WelfareRequestType,
)
from ..schemas.case_welfare import WelfareCaseUpdate


def dedupe_preserve_order(ids: list[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


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


async def apply_case_update(
    session: AsyncSession,
    applicant_id: int,
    body: WelfareCaseUpdate,
) -> Applicant:
    """Apply partial case update. Returns applicant row (caller reloads relationships)."""
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
        if a.family_distress is not None:
            applicant_row.family_distress = a.family_distress
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
            applicant_row.process_started_at = None
            applicant_row.process_sla_days = None
            applicant_row.process_completed_at = None
            applicant_row.time_count_process = None
            applicant_row.type_money_category_id = None

    if body.addresses is not None:
        await session.execute(delete(Address).where(Address.applicant_id == applicant_id))
        for addr in body.addresses:
            session.add(
                Address(
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
                    nearby_landmark=addr.nearby_landmark,
                )
            )

    if body.dependency_loads is not None:
        await session.execute(
            delete(DependencyLoad).where(DependencyLoad.applicant_id == applicant_id)
        )
        for dl in body.dependency_loads:
            session.add(
                DependencyLoad(
                    applicant_id=applicant_id,
                    dependency_type_id=dl.dependency_type_id,
                    dependency_other_text=dl.dependency_other_text,
                )
            )

    hm_count_for_update = len(body.household_members) if body.household_members is not None else None
    if body.economic_infos is not None:
        eco_id_subq = select(EconomicInfo.id).where(EconomicInfo.applicant_id == applicant_id)
        await session.execute(
            delete(EconomicIncomeSource).where(EconomicIncomeSource.economic_id.in_(eco_id_subq))
        )
        await session.execute(delete(EconomicInfo).where(EconomicInfo.applicant_id == applicant_id))
        await session.flush()
        for eco in body.economic_infos:
            econ = EconomicInfo(
                applicant_id=applicant_id,
                housing_types_id=eco.housing_types_id,
                housing_shelter=eco.housing_shelter,
                housing_types_rent=eco.housing_types_rent,
                occupation_type_id=eco.occupation_type_id,
                occupation=eco.occupation,
                monthly_income=eco.monthly_income,
                household_members=hm_count_for_update
                if hm_count_for_update is not None
                else eco.household_members,
                family_occupation_type_id=eco.family_occupation_type_id,
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

    if body.household_members is not None:
        # ใช้ upsert-by-seq แทน delete-all + recreate
        # เพื่อรักษา household_member.id ของสมาชิกเดิมไว้
        # (welfare_evidences.household_member_id FK ondelete=CASCADE — ถ้า delete แล้วสร้างใหม่ รูปหาย)
        new_seqs = {hm.seq for hm in body.household_members}

        # ดึง existing members
        existing_rows = await session.execute(
            select(HouseholdMember.id, HouseholdMember.seq)
            .where(HouseholdMember.applicant_id == applicant_id)
        )
        existing_by_seq: dict[int, int] = {row.seq: row.id for row in existing_rows}

        # ลบเฉพาะ member ที่ไม่อยู่ใน list ใหม่ (seq หายไป)
        seqs_to_delete = set(existing_by_seq.keys()) - new_seqs
        if seqs_to_delete:
            await session.execute(
                delete(HouseholdMember).where(
                    HouseholdMember.applicant_id == applicant_id,
                    HouseholdMember.seq.in_(seqs_to_delete),
                )
            )

        for hm in body.household_members:
            if hm.seq in existing_by_seq:
                # UPDATE — คง id เดิมไว้ (welfare_evidences ยังชี้ถูก)
                await session.execute(
                    sa_update(HouseholdMember)
                    .where(
                        HouseholdMember.applicant_id == applicant_id,
                        HouseholdMember.seq == hm.seq,
                    )
                    .values(
                        national_id=hm.national_id,
                        prefix_id=hm.prefix_id,
                        prefix_other=hm.prefix_other,
                        first_name=hm.first_name,
                        last_name=hm.last_name,
                        date_of_birth=hm.date_of_birth,
                        relation_to_applicant_id=hm.relation_to_applicant_id,
                        occupation_type_id=hm.occupation_type_id,
                        occupation=hm.occupation,
                        monthly_income=hm.monthly_income,
                        physical_condition=hm.physical_condition,
                        self_care=hm.self_care,
                    )
                )
            else:
                # INSERT — member ใหม่ (seq ยังไม่มีในฐานข้อมูล)
                session.add(
                    HouseholdMember(
                        applicant_id=applicant_id,
                        seq=hm.seq,
                        national_id=hm.national_id,
                        prefix_id=hm.prefix_id,
                        prefix_other=hm.prefix_other,
                        first_name=hm.first_name,
                        last_name=hm.last_name,
                        date_of_birth=hm.date_of_birth,
                        relation_to_applicant_id=hm.relation_to_applicant_id,
                        occupation_type_id=hm.occupation_type_id,
                        occupation=hm.occupation,
                        monthly_income=hm.monthly_income,
                        physical_condition=hm.physical_condition,
                        self_care=hm.self_care,
                    )
                )

        if body.economic_infos is None:
            await session.execute(
                sa_update(EconomicInfo)
                .where(EconomicInfo.applicant_id == applicant_id)
                .values(household_members=len(body.household_members))
            )

    if body.request_type_ids is not None:
        await session.execute(
            delete(WelfareRequestType).where(WelfareRequestType.applicant_id == applicant_id)
        )
        for rt in dedupe_preserve_order(body.request_type_ids):
            session.add(
                WelfareRequestType(
                    applicant_id=applicant_id,
                    request_type_id=rt,
                    request_other_text=body.request_other_text if rt == 3 else None,
                    request_in_kind_text=body.request_in_kind_text if rt == 2 else None,
                )
            )

    if body.welfare_history is not None:
        existing_wh = await session.get(WelfareHistory, applicant_id)
        wh = body.welfare_history
        if existing_wh is not None:
            existing_wh.received_count = wh.received_count
            existing_wh.has_received_welfare = wh.has_received_welfare
            existing_wh.total_received_amount = wh.total_received_amount
            await session.flush()
            await session.execute(
                delete(WelfareHistoryDetail).where(
                    WelfareHistoryDetail.welfare_history_id == applicant_id
                )
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
            session.add(
                WelfareHistoryDetail(
                    welfare_history_id=applicant_id,
                    received_welfare_type_id=det.received_welfare_type_id,
                    received_other=det.received_other,
                )
            )

    try:
        await session.flush()
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    return applicant_row
