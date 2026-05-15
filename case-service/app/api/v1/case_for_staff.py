"""ชุด API สำหรับรายการคำร้องฝั่งเจ้าหน้าที่."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import base64
import uuid
from pathlib import Path

from ...settings import resolved_upload_root
from ...api.v1.cases import _load_full_applicant, applicant_to_case_read
from ...core.database import get_session
from ...models.address import Address
from ...models.applicant import Applicant
from ...models.geo import District, Postcode, Province, SubDistrict, SubDistrictPostcode
from ...models.lookup import CurrentStatus, TypeMoneyCategory
from ...models.person import Person
from ...models.status_log import WelfareRequestStatus
from ...models.payment import ApproveCase
from ...schemas.address import AddressRead
from ...schemas.payment import ApproveCaseCreate, ApproveCaseRead
from ...schemas.case_for_staff import (
    CaseForStaffApplicantStaffFieldsRead,
    CaseForStaffApplicantStaffFieldsUpdate,
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
    PorKor1WelfareHistoryDetailRead,
    PorKor1WelfareHistoryRead,
    PorKor1WelfareRequestStatusSection,
    PorKor1WelfareRequestTypeItem,
)
from ...schemas.case_welfare import WelfareCaseRead
from ...schemas.dependency import DependencyLoadRead
from ...schemas.economic import EconomicInfoRead
from ...schemas.lookup import CurrentStatusRead, TypeMoneyCategoryRead
from ...schemas.person import PersonRead
from ...schemas.status_log import WelfareRequestStatusRead
from ...schemas.welfare import (
    WelfareEvidenceRead,
    WelfareHistoryDetailRead,
    WelfareRequestTypeRead,
)


def _save_esignature_base64(applicant_id: int, base64_str: str | None) -> str | None:
    """แปลง Base64 data URL ของลายเซ็นให้กลายเป็นไฟล์รูปภาพเก็บลง Disk และคืนค่า Relative Path (Prototype)"""
    if not base64_str or not base64_str.startswith("data:image/"):
        return base64_str

    try:
        header, encoded = base64_str.split(",", 1)
        ext = ".png"
        if "image/jpeg" in header:
            ext = ".jpg"
        elif "image/webp" in header:
            ext = ".webp"

        image_data = base64.b64decode(encoded)
        
        base_path = resolved_upload_root()
        dest_dir = (base_path / "signatures" / str(applicant_id)).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{uuid.uuid4().hex}{ext}"
        file_path = dest_dir / filename
        file_path.write_bytes(image_data)

        # เก็บเฉพาะ relative path จาก upload root ลงในฐานข้อมูล
        return f"signatures/{applicant_id}/{filename}"
    except Exception:
        # Fallback: หากเกิดปัญหา ให้ยอมเก็บ Base64 ตัวเดิมลง DB เพื่อไม่ให้ระบบล่ม
        return base64_str


def _load_esignature_base64(esignature_path: str | None) -> str | None:
    """อ่านไฟล์ภาพลายเซ็นและแปลงกลับเป็น Base64 data URL ส่งให้ frontend (Transparent Wrapper)"""
    if not esignature_path or esignature_path.startswith("data:image/"):
        return esignature_path

    try:
        base_path = resolved_upload_root()
        full_path = (base_path / esignature_path).resolve()
        
        # ตรวจเช็ค Path Traversal ป้องกันด้านความปลอดภัย
        full_path.relative_to(base_path.resolve())

        if full_path.exists() and full_path.is_file():
            ext = full_path.suffix.lower()
            mime_type = "image/png"
            if ext in [".jpg", ".jpeg"]:
                mime_type = "image/jpeg"
            elif ext == ".webp":
                mime_type = "image/webp"

            binary_data = full_path.read_bytes()
            encoded = base64.b64encode(binary_data).decode("utf-8")
            return f"data:{mime_type};base64,{encoded}"
    except Exception:
        pass
    return esignature_path


router = APIRouter(prefix="/v1/case_for_staff", tags=["case_for_staff"])

def _por_kor_1_address_geo(a: Address) -> tuple[
    int | None,
    str | None,
    int | None,
    str | None,
    int | None,
    str | None,
    str | None,
]:
    """ดึงจังหวัด/อำเภอ/ตำบล/รหัสไปรษณีย์จากความสัมพันธ์ sub_district_postcode (ต้อง selectinload แล้ว)."""
    sdp = a.sub_district_postcode
    if sdp is None:
        return (None, None, None, None, None, None, None)
    sub = sdp.sub_district
    if sub is None:
        pc = sdp.postcode
        postcode_str = pc.name if pc is not None else None
        return (None, None, None, None, None, None, postcode_str)
    dist = sub.district
    prov = dist.province if dist is not None else None
    pc = sdp.postcode
    postcode_str = pc.name if pc is not None else None
    return (
        prov.id if prov is not None else None,
        prov.name if prov is not None else None,
        dist.id if dist is not None else None,
        dist.name if dist is not None else None,
        sub.id,
        sub.name,
        postcode_str,
    )


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

    addresses = []
    for a in sorted(orm.addresses, key=lambda x: x.id):
        pid, pname, did, dname, sid, sname, pcode = _por_kor_1_address_geo(a)
        addresses.append(
            PorKor1AddressItem(
                address=AddressRead.model_validate(a),
                address_type_name=a.address_type.name if a.address_type else None,
                province_id=pid,
                province_name=pname,
                district_id=did,
                district_name=dname,
                subdistrict_id=sid,
                subdistrict_name=sname,
                postcode=pcode,
            )
        )

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

    welfare_history_section: PorKor1WelfareHistoryRead | None = None
    if case.welfare_history is not None and orm.welfare_history is not None:
        wh_orm = orm.welfare_history
        welfare_history_section = PorKor1WelfareHistoryRead(
            applicant_id=case.welfare_history.applicant_id,
            received_count=case.welfare_history.received_count,
            has_received_welfare=case.welfare_history.has_received_welfare,
            total_received_amount=case.welfare_history.total_received_amount,
            created_at=case.welfare_history.created_at,
            updated_at=case.welfare_history.updated_at,
            history_details=[
                PorKor1WelfareHistoryDetailRead(
                    **WelfareHistoryDetailRead.model_validate(d).model_dump(),
                    received_welfare_type_name=(
                        d.received_welfare_type.name if d.received_welfare_type else None
                    ),
                )
                for d in sorted(
                    wh_orm.history_details,
                    key=lambda x: (x.received_welfare_type_id, x.welfare_history_id),
                )
            ],
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
        welfare_history=welfare_history_section,
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


@router.patch(
    "/applicant-staff-fields",
    response_model=CaseForStaffApplicantStaffFieldsRead,
    summary="อัปเดตประเภทเงิน / ผู้สำรวจ SDSHV (applicants)",
    description=(
        "ใช้ `applicant_id` (query) หาแถวใน `applicants` แล้วอัปเดตเฉพาะฟิลด์ที่ส่งใน body "
        "(`type_money_category_id`, `sw_explorer_sdshv`) — ส่ง null เพื่อล้างค่า FK/ข้อความ"
    ),
)
async def update_applicant_staff_fields_for_staff(
    applicant_id: int = Query(..., ge=1, description="id จากตาราง applicants"),
    body: CaseForStaffApplicantStaffFieldsUpdate = Body(...),
    session: AsyncSession = Depends(get_session),
) -> CaseForStaffApplicantStaffFieldsRead:
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="at_least_one_field_required",
        )

    applicant = await session.get(
        Applicant,
        applicant_id,
        options=[selectinload(Applicant.type_money_category)],
    )
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    if "type_money_category_id" in payload:
        tmc_id = payload["type_money_category_id"]
        if tmc_id is not None:
            if await _get_row(session, TypeMoneyCategory, tmc_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="type_money_category_not_found",
                )
        applicant.type_money_category_id = tmc_id

    if "sw_explorer_sdshv" in payload:
        applicant.sw_explorer_sdshv = payload["sw_explorer_sdshv"]

    applicant.updated_at = datetime.now()
    await session.commit()
    result = await session.execute(
        select(Applicant)
        .where(Applicant.id == applicant_id)
        .options(selectinload(Applicant.type_money_category)),
    )
    applicant = result.scalar_one()

    tmc = applicant.type_money_category
    return CaseForStaffApplicantStaffFieldsRead(
        applicant_id=applicant.id,
        type_money_category_id=applicant.type_money_category_id,
        type_money_name=tmc.name if tmc else None,
        type_money_name_acronym=tmc.name_acronym if tmc else None,
        type_money_color=tmc.color if tmc else None,
        sw_explorer_sdshv=applicant.sw_explorer_sdshv,
        updated_at=applicant.updated_at,
    )


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
        "ดึงข้อมูลคำร้องครบถ้วน (รูปแบบจัดกลุ่มสำหรับ vsmartcare / ปศค 1) — "
        "`summary.type_money` เป็น null เมื่อ applicants.type_money_category_id ว่าง "
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

    if row.type_money_category_id is not None and row.type_money_category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="type_money_category_not_found_for_applicant",
        )

    case_read = await applicant_to_case_read(row)
    return _build_por_kor_1_detail(case_read, row)


@router.post(
    "/approve-case",
    response_model=ApproveCaseRead,
    status_code=status.HTTP_201_CREATED,
    summary="บันทึกการอนุมัติเคส (approve_case)",
    description="บันทึกประวัติการอนุมัติเคส ลายเซ็น และสถานะการอนุมัติของแต่ละ applicant",
)
async def create_approve_case_for_staff(
    body: ApproveCaseCreate,
    session: AsyncSession = Depends(get_session),
) -> ApproveCaseRead:
    applicant = await session.get(Applicant, body.applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    # 1. บันทึกลายเซ็นลง Disk แทนการยัด Base64 ลง DB โดยตรง เพื่อแก้ปัญหา DB Bloat
    final_esign = _save_esignature_base64(body.applicant_id, body.esignature)

    row = ApproveCase(
        applicant_id=body.applicant_id,
        approve_status=body.approve_status,
        esignature=final_esign,
        user_sdshv=body.user_sdshv,
    )
    session.add(row)

    # 2. อัปเดตประวัติสถานะ (Workflow Auto-transition)
    # อนุมัติ (True) -> ID 3: อยู่ระหว่างการเบิก
    # ปฏิเสธ (False) -> ID 8: ดำเนินการแก้ไขข้อมูล
    new_status_id = 3 if body.approve_status else 8
    status_log = WelfareRequestStatus(
        applicant_id=body.applicant_id,
        current_status_id=new_status_id,
        remarks="บันทึกผลการอนุมัติเคสสำเร็จ" if body.approve_status else "ปฏิเสธคำร้องขอสวัสดิการ",
        update_by_sdshv=body.user_sdshv,
    )
    session.add(status_log)

    await session.commit()
    await session.refresh(row)

    # ดึงข้อมูลและแปลง File Path กลับไปเป็น Base64 เพื่อรักษาความเข้ากันได้หน้าบ้านเดิม
    res_data = ApproveCaseRead.model_validate(row)
    res_data.esignature = _load_esignature_base64(res_data.esignature)
    return res_data


@router.get(
    "/approve-case",
    response_model=list[ApproveCaseRead],
    summary="ดึงประวัติการอนุมัติเคส",
    description="ดึงประวัติการอนุมัติของเคสตาม applicant_id เรียงตามเวลาล่าสุด",
)
async def list_approve_case_for_staff(
    applicant_id: int = Query(..., ge=1, description="id จากตาราง applicants"),
    session: AsyncSession = Depends(get_session),
) -> list[ApproveCaseRead]:
    stmt = (
        select(ApproveCase)
        .where(ApproveCase.applicant_id == applicant_id)
        .order_by(ApproveCase.id.desc())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    # วนลูปแปลง File Path กลับเป็น Base64 ให้แอปส่วนหน้าที่เป็น Legacy ใช้งานต่อได้โดยไม่ต้องแก้โค้ดดึงภาพ
    res_list = []
    for r in rows:
        d = ApproveCaseRead.model_validate(r)
        d.esignature = _load_esignature_base64(d.esignature)
        res_list.append(d)
    return res_list

