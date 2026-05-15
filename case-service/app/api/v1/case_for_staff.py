"""ชุด API สำหรับรายการคำร้องฝั่งเจ้าหน้าที่."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...api.v1.cases import _load_full_applicant, applicant_to_case_read
from ...core.database import get_session
from ...settings import settings
from ...models.address import Address
from ...models.applicant import Applicant
from ...models.geo import District, Postcode, Province, SubDistrict, SubDistrictPostcode
from ...models.lookup import CurrentStatus, TypeMoneyCategory
from ...models.person import Person
from ...models.status_log import WelfareRequestStatus
from ...schemas.address import AddressRead
from ...schemas.case_for_staff import (
    CaseForStaffListResponse,
    CaseForStaffPorKor1DetailResponse,
    CaseForStaffRead,
    CaseForStaffWelfareRequestStatusCreate,
    PorKor1AddressItem,
    PorKor1ApplicantSection,
    PorKor1DependencyItem,
    PorKor1EconomicItem,
    PorKor1EvidenceItem,
    PorKor1PersonSection,
    PorKor1Summary,
    PorKor1TypeMoney,
    PorKor1WelfareRequestStatusSection,
    PorKor1WelfareRequestTypeItem,
)
from ...schemas.case_welfare import WelfareCaseRead
from ...schemas.dependency import DependencyLoadRead
from ...schemas.economic import EconomicInfoRead
from ...schemas.lookup import CurrentStatusRead, TypeMoneyCategoryRead
from ...schemas.person import PersonRead
from ...schemas.status_log import WelfareRequestStatusRead
from ...schemas.welfare import WelfareEvidenceRead, WelfareRequestTypeRead

router = APIRouter(prefix="/v1/case_for_staff", tags=["case_for_staff"])

def _normalize_type_money_acronym(value: str | None) -> str:
    """ตัดช่องว่างหัวท้ายและรวมช่องว่างภายในสำหรับเทียบ name_acronym (เช่น 'ปศค  1' ≈ 'ปศค 1')."""
    if not value:
        return ""
    return "".join(value.split())


def _type_money_category_is_por_kor_1(category: TypeMoneyCategory | None) -> bool:
    if category is None:
        return False
    expected = _normalize_type_money_acronym(settings.por_kor_1_name_acronym)
    actual = _normalize_type_money_acronym(category.name_acronym)
    return actual.casefold() == expected.casefold()


def _build_por_kor_1_detail(case: WelfareCaseRead, orm: Applicant) -> CaseForStaffPorKor1DetailResponse:
    """จัดกลุ่ม WelfareCaseRead + ORM ที่ load relationship แล้ว เป็น response สำหรับระบบอื่น."""
    tmc = orm.type_money_category
    type_money: PorKor1TypeMoney | None = None
    if orm.type_money_category_id is not None:
        type_money = PorKor1TypeMoney(
            type_money_category_id=orm.type_money_category_id,
            name=tmc.name if tmc else None,
            name_acronym=tmc.name_acronym if tmc else None,
            color=tmc.color if tmc else None,
        )

    summary = PorKor1Summary(
        applicant_id=orm.id,
        case_number=orm.case_number,
        type_money=type_money,
        is_emergency=orm.is_emergency,
        is_existing_case=orm.is_existing_case,
        time_count_process=orm.time_count_process,
        sw_explorer_sdshv=orm.sw_explorer_sdshv,
        applicant_created_at=orm.created_at,
        applicant_updated_at=orm.updated_at,
    )

    person_orm = orm.person
    prefix_name = person_orm.prefix.name if person_orm.prefix else None
    person_section = PorKor1PersonSection(
        person=PersonRead.model_validate(person_orm),
        prefix_name=prefix_name,
    )

    applicant_section = PorKor1ApplicantSection(
        record=case.applicant,
        requester_relation_type_name=orm.requester_relation_type.name if orm.requester_relation_type else None,
        marital_status_name=orm.marital_status.name if orm.marital_status else None,
        bank_name=orm.bank_name.name if orm.bank_name else None,
    )

    addresses = [
        PorKor1AddressItem(
            address=AddressRead.model_validate(a),
            address_type_name=a.address_type.name if a.address_type else None,
        )
        for a in sorted(orm.addresses, key=lambda x: x.id)
    ]

    dependency_loads = [
        PorKor1DependencyItem(
            dependency=DependencyLoadRead.model_validate(d),
            dependency_type_name=d.dependency_type.name if d.dependency_type else None,
        )
        for d in sorted(orm.dependency_loads, key=lambda x: (x.dependency_type_id, x.applicant_id))
    ]

    economic_infos = [
        PorKor1EconomicItem(
            economic=EconomicInfoRead.model_validate(e),
            housing_type_name=e.housing_type.name if e.housing_type else None,
        )
        for e in sorted(orm.economic_infos, key=lambda x: x.id)
    ]

    welfare_request_types = [
        PorKor1WelfareRequestTypeItem(
            item=WelfareRequestTypeRead.model_validate(w),
            request_type_name=w.request_type.name if w.request_type else None,
        )
        for w in sorted(orm.welfare_request_types, key=lambda x: x.request_type_id)
    ]

    welfare_request_status = PorKor1WelfareRequestStatusSection(
        latest=case.latest_welfare_request_status,
        history=case.welfare_request_status_logs,
    )

    evidences = [
        PorKor1EvidenceItem(
            evidence=WelfareEvidenceRead.model_validate(ev),
            attachment_type_name=ev.attachment_type.name if ev.attachment_type else None,
            view_path=f"/v1/cases/{orm.id}/evidences/{ev.id}/file",
        )
        for ev in sorted(orm.welfare_evidences, key=lambda x: x.id)
    ]

    return CaseForStaffPorKor1DetailResponse(
        summary=summary,
        person=person_section,
        applicant=applicant_section,
        addresses=addresses,
        dependency_loads=dependency_loads,
        economic_infos=economic_infos,
        welfare_request_types=welfare_request_types,
        welfare_history=case.welfare_history,
        welfare_request_status=welfare_request_status,
        evidences=evidences,
    )


def _clean_text_filter(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


async def _get_row(session: AsyncSession, model: object, row_id: int) -> object | None:
    result = await session.execute(select(model).where(model.id == row_id))  # type: ignore[attr-defined]
    return result.scalar_one_or_none()


@router.get("", response_model=CaseForStaffListResponse)
async def list_cases_for_staff(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการค้นหา"),
    case_number: str | None = Query(None, description="ค้นหาจากเลข case"),
    current_status: str | None = Query(None, description="ค้นหาจากข้อความสถานะฝั่งเจ้าหน้าที่"),
    firstname: str | None = Query(None, description="ค้นหาจากชื่อ"),
    lastname: str | None = Query(None, description="ค้นหาจากนามสกุล"),
    cid: str | None = Query(None, description="ค้นหาจากเลขบัตรประชาชน"),
    datetime_create: date | None = Query(None, description="วันที่สร้าง case (YYYY-MM-DD)"),
    province_name: str | None = Query(None, description="ค้นหาจากชื่อจังหวัด"),
    district_id: int | None = Query(None, description="กรองตามอำเภอ"),
    district_name: str | None = Query(None, description="ค้นหาจากชื่ออำเภอ"),
    subdistrict_id: int | None = Query(None, description="กรองตามตำบล"),
    subdistrict_name: str | None = Query(None, description="ค้นหาจากชื่อตำบล"),
    subdistrict_postcode_id: int | None = Query(None, description="กรองตามแถว bridge sub_districts_postcode"),
    postcode: str | None = Query(None, description="ค้นหาจากรหัสไปรษณีย์"),
    type_money_id: int | None = Query(None, description="กรองตาม type_money_category.id (applicants.type_money_category_id)"),
    session: AsyncSession = Depends(get_session),
) -> CaseForStaffListResponse:
    province = await session.scalar(select(Province).where(Province.id == province_id))
    if province is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="province_not_found")

    latest_status_sq = (
        select(
            WelfareRequestStatus.applicant_id.label("applicant_id"),
            WelfareRequestStatus.current_status_id.label("current_status_id"),
            CurrentStatus.description_staff.label("current_status"),
            func.row_number()
            .over(
                partition_by=WelfareRequestStatus.applicant_id,
                order_by=[WelfareRequestStatus.updated_at.desc(), WelfareRequestStatus.id.desc()],
            )
            .label("rn"),
        )
        .join(CurrentStatus, CurrentStatus.id == WelfareRequestStatus.current_status_id)
        .subquery()
    )

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
        select(
            Applicant.id.label("applicant_id"),
            Applicant.case_number.label("case_number"),
            latest_status_sq.c.current_status_id.label("current_status_id"),
            latest_status_sq.c.current_status.label("current_status"),
            Applicant.type_money_category_id.label("type_money_id"),
            TypeMoneyCategory.name.label("type_money_id_name"),
            TypeMoneyCategory.color.label("type_money_id_color"),
            TypeMoneyCategory.name_acronym.label("type_money_name_acronym"),
            Applicant.sw_explorer_sdshv.label("sw_explorer_sdshv"),
            Person.first_name.label("firstname"),
            Person.last_name.label("lastname"),
            Person.cid.label("cid"),
            Applicant.created_at.label("datetime_create"),
            Applicant.is_emergency.label("is_emergency"),
            Applicant.is_existing_case.label("is_existing_case"),
            Applicant.time_count_process.label("time_count_process"),
            Province.id.label("province_id"),
            Province.name.label("province_name"),
            District.id.label("district_id"),
            District.name.label("district_name"),
            SubDistrict.id.label("subdistrict_id"),
            SubDistrict.name.label("subdistrict_name"),
            SubDistrictPostcode.id.label("subdistrict_postcode_id"),
            Postcode.name.label("postcode"),
        )
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
        .outerjoin(TypeMoneyCategory, TypeMoneyCategory.id == Applicant.type_money_category_id)
        .where(Province.id == province_id)
        .order_by(Applicant.created_at.desc(), Applicant.id.desc())
    )

    total_stmt = select(func.count()).select_from(
        stmt.with_only_columns(Applicant.id).order_by(None).distinct().subquery()
    )

    if cleaned_case_number := _clean_text_filter(case_number):
        stmt = stmt.where(Applicant.case_number.ilike(f"%{cleaned_case_number}%"))
    if cleaned_current_status := _clean_text_filter(current_status):
        stmt = stmt.where(latest_status_sq.c.current_status.ilike(f"%{cleaned_current_status}%"))
    if cleaned_firstname := _clean_text_filter(firstname):
        stmt = stmt.where(Person.first_name.ilike(f"%{cleaned_firstname}%"))
    if cleaned_lastname := _clean_text_filter(lastname):
        stmt = stmt.where(Person.last_name.ilike(f"%{cleaned_lastname}%"))
    if cleaned_cid := _clean_text_filter(cid):
        stmt = stmt.where(Person.cid.ilike(f"%{cleaned_cid}%"))
    if datetime_create is not None:
        stmt = stmt.where(func.date(Applicant.created_at) == datetime_create)
    if cleaned_province_name := _clean_text_filter(province_name):
        stmt = stmt.where(Province.name.ilike(f"%{cleaned_province_name}%"))
    if district_id is not None:
        stmt = stmt.where(District.id == district_id)
    if cleaned_district_name := _clean_text_filter(district_name):
        stmt = stmt.where(District.name.ilike(f"%{cleaned_district_name}%"))
    if subdistrict_id is not None:
        stmt = stmt.where(SubDistrict.id == subdistrict_id)
    if cleaned_subdistrict_name := _clean_text_filter(subdistrict_name):
        stmt = stmt.where(SubDistrict.name.ilike(f"%{cleaned_subdistrict_name}%"))
    if subdistrict_postcode_id is not None:
        stmt = stmt.where(SubDistrictPostcode.id == subdistrict_postcode_id)
    if cleaned_postcode := _clean_text_filter(postcode):
        stmt = stmt.where(Postcode.name.ilike(f"%{cleaned_postcode}%"))
    if type_money_id is not None:
        stmt = stmt.where(Applicant.type_money_category_id == type_money_id)

    filtered_count_stmt = select(func.count()).select_from(
        stmt.with_only_columns(Applicant.id).order_by(None).distinct().subquery()
    )

    total_applicants = await session.scalar(total_stmt)
    filtered_applicants = await session.scalar(filtered_count_stmt)
    result = await session.execute(stmt)
    rows = result.mappings().all()
    return CaseForStaffListResponse(
        province_id=province.id,
        province_name=province.name,
        total_applicants=total_applicants or 0,
        filtered_applicants=filtered_applicants or 0,
        items=[CaseForStaffRead.model_validate(row) for row in rows],
    )


@router.get("/type-money-categories", response_model=list[TypeMoneyCategoryRead])
async def list_type_money_categories(
    session: AsyncSession = Depends(get_session),
) -> list[TypeMoneyCategoryRead]:
    result = await session.execute(select(TypeMoneyCategory).order_by(TypeMoneyCategory.id))
    return [TypeMoneyCategoryRead.model_validate(row) for row in result.scalars().all()]


@router.get(
    "/type-money-categories/{type_money_category_id}",
    response_model=TypeMoneyCategoryRead,
)
async def get_type_money_category(
    type_money_category_id: int,
    session: AsyncSession = Depends(get_session),
) -> TypeMoneyCategoryRead:
    row = await _get_row(session, TypeMoneyCategory, type_money_category_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="type_money_category_not_found")
    return TypeMoneyCategoryRead.model_validate(row)


@router.get("/current-status", response_model=list[CurrentStatusRead])
async def list_current_status_for_staff(
    session: AsyncSession = Depends(get_session),
) -> list[CurrentStatusRead]:
    result = await session.execute(
        select(CurrentStatus).order_by(CurrentStatus.filter_order.asc(), CurrentStatus.id.asc()),
    )
    return [CurrentStatusRead.model_validate(row) for row in result.scalars().all()]


@router.get("/current-status/{current_status_id}", response_model=CurrentStatusRead)
async def get_current_status_for_staff(
    current_status_id: int,
    session: AsyncSession = Depends(get_session),
) -> CurrentStatusRead:
    row = await _get_row(session, CurrentStatus, current_status_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="current_status_not_found")
    return CurrentStatusRead.model_validate(row)


@router.post(
    "/welfare-request-status",
    response_model=WelfareRequestStatusRead,
    status_code=status.HTTP_201_CREATED,
    summary="บันทึกสถานะคำร้อง (welfare_request_status)",
    description=(
        "รับ applicant_id และ current_status_id — ตรวจจากตาราง applicants / current_status "
        "แล้วเพิ่มแถวใน welfare_request_status (สถานะล่าสุดใช้แถวล่าสุดตามเวลา)"
    ),
)
async def create_welfare_request_status_for_staff(
    body: CaseForStaffWelfareRequestStatusCreate,
    session: AsyncSession = Depends(get_session),
) -> WelfareRequestStatusRead:
    applicant = await session.get(Applicant, body.applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")
    if await _get_row(session, CurrentStatus, body.current_status_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="current_status_not_found")

    log = WelfareRequestStatus(
        applicant_id=body.applicant_id,
        current_status_id=body.current_status_id,
        remarks=body.remarks,
        update_by_sdshv=body.update_by_sdshv,
    )
    session.add(log)
    await session.commit()
    result = await session.execute(
        select(WelfareRequestStatus)
        .where(WelfareRequestStatus.id == log.id)
        .options(selectinload(WelfareRequestStatus.current_status)),
    )
    row = result.scalar_one()
    return WelfareRequestStatusRead.model_validate(row)


@router.get(
    "/por-kor-1-detail",
    response_model=CaseForStaffPorKor1DetailResponse,
    summary="รายละเอียดคำร้อง ปศค 1 สำหรับระบบอื่น (จัดกลุ่มข้อมูล)",
    description=(
        "ดึงข้อมูลคำร้องครบถ้วน — `summary.type_money` เป็น null เมื่อ applicants.type_money_category_id ว่าง "
        "ถ้ามีประเภทเงินต้องเป็น ปศค 1 ตาม `POR_KOR_1_NAME_ACRONYM` (หลัง normalize ช่องว่าง) "
        "จัดเป็นกลุ่ม: สรุปคำร้อง, ข้อมูลบุคคล, ข้อมูลผู้ขอ, ที่อยู่, ภาระเลี้ยงดู, เศรษฐกิจ, "
        "ประเภทคำร้อง, ประวัติสวัสดิการ, สถานะ, หลักฐานพร้อม path สำหรับ GET รูป"
    ),
)
async def get_por_kor_1_case_detail_for_staff(
    applicant_id: int = Query(..., ge=1, description="id จากตาราง applicants"),
    session: AsyncSession = Depends(get_session),
) -> CaseForStaffPorKor1DetailResponse:
    row = await _load_full_applicant(session, applicant_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    category = row.type_money_category

    if row.type_money_category_id is not None:
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="type_money_category_not_found_for_applicant",
            )
        if not _type_money_category_is_por_kor_1(category):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_por_kor_1_case")

    case_read = await applicant_to_case_read(row)
    return _build_por_kor_1_detail(case_read, row)
