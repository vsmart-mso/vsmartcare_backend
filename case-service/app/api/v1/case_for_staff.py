"""ชุด API สำหรับรายการคำร้องฝั่งเจ้าหน้าที่."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, case as sql_case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import base64
import uuid
from pathlib import Path
from uuid import UUID

from ...settings import resolved_upload_root
from ...api.v1.cases import _load_full_applicant, applicant_to_case_read
from ...core.database import get_session
from ...models.address import Address
from ...models.applicant import Applicant
from ...models.geo import District, Postcode, Province, SubDistrict, SubDistrictPostcode
from ...models.lookup import AttachmentType, BankName, CurrentStatus, TypeMoneyCategory
from ...models.person import Person
from ...models.status_log import WelfareRequestStatus
from ...models.intake import CaseHandling, CaseRegulationChoice
from ...models.payment import ApproveCase, FilePayment, WelfareDdaRef, WelfarePayment
from ...services.process_sla import (
    apply_emergency_flag_for_money_category,
    apply_process_sla_to_applicant,
    process_sla_fields_dict,
)
from ...constants.current_status import CURRENT_STATUS_WITHDRAWING
from ...services.file_payment_upload import (
    file_payment_upload_root,
    save_file_payment_pdf,
)
from ...services.payment_upload_history import build_payment_upload_history
from ...services.welfare_payment_flow import (
    apply_037_update,
    apply_038_update,
    apply_fields_on_active_dda,
    apply_payment_update_by_id,
    file_payment_owned_by_applicant,
)
from ...schemas.address import AddressRead
from ...schemas.payment import (
    ApproveCaseCreate,
    ApproveCaseRead,
    FilePaymentRead,
    FilePaymentUploadRead,
    WelfareDdaRefBundleCreate,
    WelfareDdaRefBundleRead,
    PaymentUploadHistoryRead,
    WelfarePaymentInitialRead,
    WelfarePaymentRead,
    WelfarePaymentUpdate,
)
from ...schemas.case_for_staff import (
    CaseForStaffApplicantStaffFieldsRead,
    CaseForStaffApplicantStaffFieldsUpdate,
    CaseForStaffFinanceListResponse,
    CaseForStaffFinanceRead,
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
from ...schemas.lookup import AttachmentTypeRead, CurrentStatusRead, TypeMoneyCategoryRead
from ...schemas.person import PersonRead
from ...models.review import ReviewField, WelfareReviewComment
from ...schemas.review import (
    ReviewFieldRead,
    WelfareEditRequestCreate,
    WelfareEditRequestRead,
    WelfareReviewCommentRead,
)
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


def _enrich_row_process_sla(data: dict[str, object]) -> None:
    data.update(
        process_sla_fields_dict(
            data.get("process_started_at"),  # type: ignore[arg-type]
            data.get("process_sla_days"),  # type: ignore[arg-type]
        ),
    )


def _row_to_case_for_staff_read(row: object) -> CaseForStaffRead:
    data = dict(row)  # type: ignore[arg-type]
    _enrich_row_process_sla(data)
    return CaseForStaffRead.model_validate(data)


def _row_to_case_for_staff_finance_read(row: object) -> CaseForStaffFinanceRead:
    data = dict(row)  # type: ignore[arg-type]
    _enrich_row_process_sla(data)
    return CaseForStaffFinanceRead.model_validate(data)


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
        sw_explorer_sdshv=orm.sw_explorer_sdshv,
        applicant_created_at=orm.created_at,
        applicant_updated_at=orm.updated_at,
        **process_sla_fields_dict(orm.process_started_at, orm.process_sla_days),
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

    reg_money = None
    if orm.case_handling is not None and orm.case_handling.regulation_choice is not None:
        reg_money = orm.case_handling.regulation_choice.money_amount

    welfare_request_types = [
        PorKor1WelfareRequestTypeItem(
            item=WelfareRequestTypeRead.model_validate(w),
            request_type_name=w.request_type.name if w.request_type else None,
            request_other_text=w.request_other_text,
            money_amount=reg_money,
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


def _welfare_payment_stats_subquery():
    return (
        select(
            WelfarePayment.applicant_id.label("applicant_id"),
            func.coalesce(
                func.sum(sql_case((WelfarePayment.is_037_or_038.is_(False), 1), else_=0)),
                0,
            ).label("count_037"),
            func.coalesce(
                func.sum(sql_case((WelfarePayment.is_037_or_038.is_(True), 1), else_=0)),
                0,
            ).label("count_038"),
        )
        .group_by(WelfarePayment.applicant_id)
        .subquery()
    )


def _latest_welfare_payment_subquery():
    return (
        select(
            WelfarePayment.applicant_id.label("applicant_id"),
            WelfarePayment.is_037_or_038.label("is_037_or_038"),
            func.row_number()
            .over(
                partition_by=WelfarePayment.applicant_id,
                order_by=WelfarePayment.id.desc(),
            )
            .label("rn"),
        )
        .subquery()
    )


def _applicant_have_dda_ref_exists():
    """มีแถว welfare_payment ที่ผูก welfare_dda_ref สำหรับ applicant นี้หรือไม่."""
    return (
        select(WelfarePayment.id)
        .where(WelfarePayment.applicant_id == Applicant.id)
        .join(WelfareDdaRef, WelfareDdaRef.id == WelfarePayment.dda_ref_id)
        .exists()
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


async def _get_row(session: AsyncSession, model: object, row_id: int) -> object | None:
    result = await session.execute(select(model).where(model.id == row_id))  # type: ignore[attr-defined]
    return result.scalar_one_or_none()


def _welfare_payment_update_indicates_037(updates: dict) -> bool:
    """True เมื่อ request บันทึกผลจ่ายแบบ 037 (is_037_or_038 = false)."""
    return updates.get("is_037_or_038") is False


def _welfare_payment_update_indicates_038(updates: dict) -> bool:
    """True เมื่อ request บันทึกผลจ่ายแบบ 038 (is_037_or_038 = true)."""
    return updates.get("is_037_or_038") is True


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
            CurrentStatus.color.label("current_status_color"),
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

    payment_stats_sq = _welfare_payment_stats_subquery()
    latest_payment_sq = _latest_welfare_payment_subquery()
    have_dda_ref = _applicant_have_dda_ref_exists()
    is_approved = _applicant_is_approved_exists()

    stmt = (
        select(
            Applicant.id.label("applicant_id"),
            Applicant.case_number.label("case_number"),
            latest_status_sq.c.current_status_id.label("current_status_id"),
            latest_status_sq.c.current_status.label("current_status"),
            latest_status_sq.c.current_status_color.label("current_status_color"),
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
            Applicant.process_started_at.label("process_started_at"),
            Applicant.process_sla_days.label("process_sla_days"),
            Province.id.label("province_id"),
            Province.name.label("province_name"),
            District.id.label("district_id"),
            District.name.label("district_name"),
            SubDistrict.id.label("subdistrict_id"),
            SubDistrict.name.label("subdistrict_name"),
            SubDistrictPostcode.id.label("subdistrict_postcode_id"),
            Postcode.name.label("postcode"),
            func.coalesce(payment_stats_sq.c.count_037, 0).label("count_037"),
            func.coalesce(payment_stats_sq.c.count_038, 0).label("count_038"),
            latest_payment_sq.c.is_037_or_038.label("is_037_or_038"),
            have_dda_ref.label("have_dda_ref"),
            is_approved.label("is_approved"),
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
        .outerjoin(
            payment_stats_sq,
            payment_stats_sq.c.applicant_id == Applicant.id,
        )
        .outerjoin(
            latest_payment_sq,
            and_(
                latest_payment_sq.c.applicant_id == Applicant.id,
                latest_payment_sq.c.rn == 1,
            ),
        )
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
        items=[_row_to_case_for_staff_read(row) for row in rows],
    )


async def _list_cases_for_staff_finance_impl(
    session: AsyncSession,
    province_id: int,
    case_number: str | None,
    current_status: str | None,
    current_status_id: list[int] | None,
    firstname: str | None,
    lastname: str | None,
    cid: str | None,
    datetime_create: date | None,
    province_name: str | None,
    district_id: int | None,
    district_name: str | None,
    subdistrict_id: int | None,
    subdistrict_name: str | None,
    subdistrict_postcode_id: int | None,
    postcode: str | None,
    type_money_id: list[int] | None,
    *,
    require_welfare_payment_with_dda: bool,
) -> CaseForStaffFinanceListResponse:
    province = await session.scalar(select(Province).where(Province.id == province_id))
    if province is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="province_not_found")

    latest_status_sq = (
        select(
            WelfareRequestStatus.applicant_id.label("applicant_id"),
            WelfareRequestStatus.current_status_id.label("current_status_id"),
            CurrentStatus.description_staff.label("current_status"),
            CurrentStatus.color.label("current_status_color"),
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

    payment_stats_sq = _welfare_payment_stats_subquery()
    latest_payment_sq = _latest_welfare_payment_subquery()

    latest_dda_sq = (
        select(
            WelfarePayment.applicant_id.label("applicant_id"),
            WelfareDdaRef.dda_ref.label("dda_ref"),
            func.row_number()
            .over(
                partition_by=WelfarePayment.applicant_id,
                order_by=WelfarePayment.id.desc(),
            )
            .label("rn"),
        )
        .join(WelfareDdaRef, WelfareDdaRef.id == WelfarePayment.dda_ref_id)
        .subquery()
    )

    approved_exists = _applicant_is_approved_exists()
    is_approved = approved_exists

    welfare_payment_with_dda_exists = _applicant_have_dda_ref_exists()

    stmt = (
        select(
            Applicant.id.label("applicant_id"),
            Applicant.case_number.label("case_number"),
            latest_status_sq.c.current_status_id.label("current_status_id"),
            latest_status_sq.c.current_status.label("current_status"),
            latest_status_sq.c.current_status_color.label("current_status_color"),
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
            Applicant.process_started_at.label("process_started_at"),
            Applicant.process_sla_days.label("process_sla_days"),
            Province.id.label("province_id"),
            Province.name.label("province_name"),
            District.id.label("district_id"),
            District.name.label("district_name"),
            SubDistrict.id.label("subdistrict_id"),
            SubDistrict.name.label("subdistrict_name"),
            SubDistrictPostcode.id.label("subdistrict_postcode_id"),
            Postcode.name.label("postcode"),
            latest_dda_sq.c.dda_ref.label("dda_ref"),
            func.coalesce(payment_stats_sq.c.count_037, 0).label("count_037"),
            func.coalesce(payment_stats_sq.c.count_038, 0).label("count_038"),
            latest_payment_sq.c.is_037_or_038.label("is_037_or_038"),
            welfare_payment_with_dda_exists.label("have_dda_ref"),
            is_approved.label("is_approved"),
            Applicant.bank_name_id.label("bank_name_id"),
            BankName.bank_code.label("bank_code"),
            Applicant.bank_account_no.label("bank_account_no"),
            Applicant.email_address.label("email_address"),
            Applicant.mobile_phone.label("mobile_phone"),
            CaseRegulationChoice.money_amount.label("money_amount"),
        )
        .join(Person, Person.id == Applicant.persons_id)
        .outerjoin(BankName, BankName.id == Applicant.bank_name_id)
        .outerjoin(CaseHandling, CaseHandling.applicant_id == Applicant.id)
        .outerjoin(
            CaseRegulationChoice,
            CaseRegulationChoice.case_handling_id == CaseHandling.id,
        )
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
        .outerjoin(
            payment_stats_sq,
            payment_stats_sq.c.applicant_id == Applicant.id,
        )
        .outerjoin(
            latest_dda_sq,
            and_(
                latest_dda_sq.c.applicant_id == Applicant.id,
                latest_dda_sq.c.rn == 1,
            ),
        )
        .outerjoin(
            latest_payment_sq,
            and_(
                latest_payment_sq.c.applicant_id == Applicant.id,
                latest_payment_sq.c.rn == 1,
            ),
        )
        .where(Province.id == province_id)
        .where(approved_exists)
        .order_by(Applicant.created_at.desc(), Applicant.id.desc())
    )
    if require_welfare_payment_with_dda:
        stmt = stmt.where(welfare_payment_with_dda_exists)
        stmt = stmt.where(
            or_(
                latest_status_sq.c.current_status_id.is_(None),
                latest_status_sq.c.current_status_id < CURRENT_STATUS_WITHDRAWING,
            ),
        )

    total_stmt = select(func.count()).select_from(
        stmt.with_only_columns(Applicant.id).order_by(None).distinct().subquery()
    )

    if cleaned_case_number := _clean_text_filter(case_number):
        stmt = stmt.where(Applicant.case_number.ilike(f"%{cleaned_case_number}%"))
    if cleaned_current_status := _clean_text_filter(current_status):
        stmt = stmt.where(latest_status_sq.c.current_status.ilike(f"%{cleaned_current_status}%"))
    if current_status_id:
        stmt = stmt.where(latest_status_sq.c.current_status_id.in_(current_status_id))
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
    if type_money_id:
        stmt = stmt.where(Applicant.type_money_category_id.in_(type_money_id))

    filtered_count_stmt = select(func.count()).select_from(
        stmt.with_only_columns(Applicant.id).order_by(None).distinct().subquery()
    )

    total_applicants = await session.scalar(total_stmt)
    filtered_applicants = await session.scalar(filtered_count_stmt)
    result = await session.execute(stmt)
    rows = result.mappings().all()
    return CaseForStaffFinanceListResponse(
        province_id=province.id,
        province_name=province.name,
        total_applicants=total_applicants or 0,
        filtered_applicants=filtered_applicants or 0,
        items=[_row_to_case_for_staff_finance_read(row) for row in rows],
    )


@router.get("/finance", response_model=CaseForStaffFinanceListResponse)
async def list_cases_for_staff_finance(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการค้นหา (บังคับ)"),
    case_number: str | None = Query(None, description="ค้นหาจากเลข case"),
    current_status: str | None = Query(None, description="ค้นหาจากข้อความสถานะฝั่งเจ้าหน้าที่"),
    current_status_id: list[int] | None = Query(
        None,
        description="กรองตาม current_status_id ได้หลายค่า (เช่น ?current_status_id=1&current_status_id=2)",
    ),
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
    type_money_id: list[int] | None = Query(
        None,
        description="กรองตาม type_money_category.id ได้หลายค่า (เช่น ?type_money_id=1&type_money_id=2)",
    ),
    session: AsyncSession = Depends(get_session),
) -> CaseForStaffFinanceListResponse:
    """รายการสำหรับตารางการเงิน — เฉพาะเคสที่ approve_case.approve_status = true."""
    return await _list_cases_for_staff_finance_impl(
        session,
        province_id,
        case_number,
        current_status,
        current_status_id,
        firstname,
        lastname,
        cid,
        datetime_create,
        province_name,
        district_id,
        district_name,
        subdistrict_id,
        subdistrict_name,
        subdistrict_postcode_id,
        postcode,
        type_money_id,
        require_welfare_payment_with_dda=False,
    )


@router.get("/finance/with-dda-ref", response_model=CaseForStaffFinanceListResponse)
async def list_cases_for_staff_finance_with_dda_ref(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการค้นหา (บังคับ)"),
    case_number: str | None = Query(None, description="ค้นหาจากเลข case"),
    current_status: str | None = Query(None, description="ค้นหาจากข้อความสถานะฝั่งเจ้าหน้าที่"),
    current_status_id: list[int] | None = Query(
        None,
        description="กรองตาม current_status_id ได้หลายค่า",
    ),
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
    type_money_id: list[int] | None = Query(
        None,
        description="กรองตาม type_money_category.id ได้หลายค่า",
    ),
    session: AsyncSession = Depends(get_session),
) -> CaseForStaffFinanceListResponse:
    """เหมือน /finance แต่ดึงเฉพาะ applicant ที่มี welfare_payment ผูก welfare_dda_ref แล้ว.

    ไม่รวมเคสที่สถานะล่าสุด current_status_id >= 10 (อยู่ระหว่างการเบิกขึ้นไป).
    """
    return await _list_cases_for_staff_finance_impl(
        session,
        province_id,
        case_number,
        current_status,
        current_status_id,
        firstname,
        lastname,
        cid,
        datetime_create,
        province_name,
        district_id,
        district_name,
        subdistrict_id,
        subdistrict_name,
        subdistrict_postcode_id,
        postcode,
        type_money_id,
        require_welfare_payment_with_dda=True,
    )


@router.patch("/welfare-payment", response_model=WelfarePaymentRead)
async def update_welfare_payment_for_staff(
    applicant_id: int = Query(..., ge=1, description="id จากตาราง applicants"),
    body: WelfarePaymentUpdate = Body(...),
    session: AsyncSession = Depends(get_session),
) -> WelfarePaymentRead:
    """บันทึก 037/038 ตามกฎรอบ DDA — คืนแถว welfare_payment ที่ถูกสร้างหรือแก้ (ใช้ id อัปโหลด PDF).

    038 ครั้งแรก: PATCH แถว is_037_or_038=null จาก bundle; ครั้งถัดไป: INSERT แถวใหม่
    037: ครั้งเดียวต่อรอบ DDA — ถ้าบันทึก 037 จะเพิ่ม welfare_request_status เป็น current_status_id=10
    """
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="no_fields_to_update")

    if _welfare_payment_update_indicates_037(updates):
        payment = await apply_037_update(session, applicant_id, updates)
    elif _welfare_payment_update_indicates_038(updates):
        payment = await apply_038_update(session, applicant_id, updates)
    else:
        payment = await apply_fields_on_active_dda(session, applicant_id, updates)

    is_037_update = _welfare_payment_update_indicates_037(updates)

    if is_037_update:
        if await _get_row(session, CurrentStatus, CURRENT_STATUS_WITHDRAWING) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="current_status_not_found")
        session.add(
            WelfareRequestStatus(
                applicant_id=applicant_id,
                current_status_id=CURRENT_STATUS_WITHDRAWING,
                remarks="บันทึกผลจ่ายเงิน 037",
                update_by_sdshv=updates.get("user_sdshv"),
            ),
        )

    await session.commit()
    await session.refresh(payment)
    return WelfarePaymentRead.model_validate(payment)


@router.patch(
    "/welfare-payment/{welfare_payment_id}",
    response_model=WelfarePaymentRead,
    summary="อัปเดต welfare_payment ตาม id (แก้ไขรอบเดิม)",
)
async def update_welfare_payment_by_id_for_staff(
    welfare_payment_id: int,
    applicant_id: int = Query(..., ge=1, description="id จากตาราง applicants"),
    body: WelfarePaymentUpdate = Body(...),
    session: AsyncSession = Depends(get_session),
) -> WelfarePaymentRead:
    """PATCH แถวที่ระบุโดยตรง — ใช้แก้ประวัติ payment-upload-history ไม่สร้างแถว 038 ใหม่."""
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="no_fields_to_update")

    payment = await apply_payment_update_by_id(
        session,
        applicant_id,
        welfare_payment_id,
        updates,
    )
    await session.commit()
    await session.refresh(payment)
    return WelfarePaymentRead.model_validate(payment)


@router.post(
    "/applicant/{applicant_id}/file-payment",
    response_model=FilePaymentUploadRead,
    status_code=status.HTTP_201_CREATED,
    summary="อัปโหลดไฟล์ PDF สำหรับ applicant (file_payment)",
)
async def upload_file_payment_pdf(
    applicant_id: int,
    attachment_type_id: int = Form(..., ge=1),
    welfare_payment_id: int | None = Form(
        None,
        ge=1,
        description="id จาก welfare_payment หลัง PATCH — ไม่ส่งจะเลือกแถว 037 หรือ 038 ตาม attachment_type_id",
    ),
    file_payment_id: int | None = Form(
        None,
        ge=1,
        description="แก้ไขประวัติ — อัปเดตแถว file_payment เดิม ไม่สร้างแถวใหม่",
    ),
    upload_batch_id: UUID | None = Form(
        None,
        description="UUID ร่วมกันต่อการบันทึกครั้งเดียวใน modal",
    ),
    file: UploadFile = File(..., description="ไฟล์ PDF"),
    session: AsyncSession = Depends(get_session),
) -> FilePaymentUploadRead:
    row = await save_file_payment_pdf(
        session,
        applicant_id=applicant_id,
        attachment_type_id=attachment_type_id,
        file=file,
        welfare_payment_id=welfare_payment_id,
        upload_batch_id=upload_batch_id,
        file_payment_id=file_payment_id,
    )
    return FilePaymentUploadRead(
        **FilePaymentRead.model_validate(row).model_dump(),
        view_path=(
            f"/v1/case_for_staff/applicant/{applicant_id}/file-payment/{row.id}/file"
        ),
    )


@router.get(
    "/applicant/{applicant_id}/file-payment/{file_payment_id}/file",
    summary="ดาวน์โหลดไฟล์ PDF ของ file_payment",
    response_class=FileResponse,
)
async def get_file_payment_pdf(
    applicant_id: int,
    file_payment_id: int,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    row = await session.get(FilePayment, file_payment_id)
    if row is None or not await file_payment_owned_by_applicant(session, applicant_id, row):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file_payment_not_found")

    root = file_payment_upload_root()
    path = (root / row.file_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file_payment_invalid_path",
        ) from e
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file_payment_file_missing")

    download_name = row.file_original_name or row.file_stored_name or path.name
    return FileResponse(path, media_type="application/pdf", filename=download_name)


@router.get(
    "/applicant/{applicant_id}/welfare-payments",
    response_model=list[WelfarePaymentRead],
    summary="รายการ welfare_payment ของ applicant",
)
async def list_welfare_payments_for_applicant(
    applicant_id: int,
    dda_ref_id: int | None = Query(None, ge=1, description="กรองตาม welfare_dda_ref.id"),
    session: AsyncSession = Depends(get_session),
) -> list[WelfarePaymentRead]:
    stmt = select(WelfarePayment).where(WelfarePayment.applicant_id == applicant_id)
    if dda_ref_id is not None:
        stmt = stmt.where(WelfarePayment.dda_ref_id == dda_ref_id)
    stmt = stmt.order_by(WelfarePayment.id.asc())
    result = await session.execute(stmt)
    return [WelfarePaymentRead.model_validate(row) for row in result.scalars().all()]


@router.get(
    "/applicant/{applicant_id}/file-payments",
    response_model=list[FilePaymentUploadRead],
    summary="รายการ file_payment ของ applicant",
)
async def list_file_payments_for_applicant(
    applicant_id: int,
    welfare_payment_id: int | None = Query(None, ge=1),
    attachment_type_id: int | None = Query(None, ge=1),
    session: AsyncSession = Depends(get_session),
) -> list[FilePaymentUploadRead]:
    linked_payment_ids = select(WelfarePayment.id).where(
        WelfarePayment.applicant_id == applicant_id,
    )
    applicant_dda_ids = select(WelfarePayment.dda_ref_id).where(
        WelfarePayment.applicant_id == applicant_id,
    )
    stmt = select(FilePayment).where(
        or_(
            FilePayment.welfare_payment_id.in_(linked_payment_ids),
            and_(
                FilePayment.welfare_payment_id.is_(None),
                FilePayment.welfare_dda_ref_id.in_(applicant_dda_ids),
            ),
        ),
    )
    if welfare_payment_id is not None:
        stmt = stmt.where(FilePayment.welfare_payment_id == welfare_payment_id)
    if attachment_type_id is not None:
        stmt = stmt.where(FilePayment.attachment_type_id == attachment_type_id)
    stmt = stmt.order_by(FilePayment.id.asc())
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        FilePaymentUploadRead(
            **FilePaymentRead.model_validate(row).model_dump(),
            view_path=(
                f"/v1/case_for_staff/applicant/{applicant_id}/file-payment/{row.id}/file"
            ),
        )
        for row in rows
    ]


@router.get(
    "/applicant/{applicant_id}/payment-upload-history",
    response_model=PaymentUploadHistoryRead,
    summary="ประวัติการอัปโหลด PDF 037/038",
    description=(
        "จัดกลุ่มตาม upload_batch_id หรือรอบ 037/038 — คืนหมายเลขคำร้อง, "
        "Payment ID, transaction_date, effective_date, ไฟล์และ view_path"
    ),
)
async def get_payment_upload_history(
    applicant_id: int,
    session: AsyncSession = Depends(get_session),
) -> PaymentUploadHistoryRead:
    return await build_payment_upload_history(session, applicant_id)


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


@router.get("/attachment-types", response_model=list[AttachmentTypeRead])
async def list_attachment_types_for_staff(
    session: AsyncSession = Depends(get_session),
) -> list[AttachmentTypeRead]:
    result = await session.execute(select(AttachmentType).order_by(AttachmentType.id))
    return [AttachmentTypeRead.model_validate(row) for row in result.scalars().all()]


@router.get(
    "/attachment-types/{attachment_type_id}",
    response_model=AttachmentTypeRead,
)
async def get_attachment_type_for_staff(
    attachment_type_id: int,
    session: AsyncSession = Depends(get_session),
) -> AttachmentTypeRead:
    row = await _get_row(session, AttachmentType, attachment_type_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attachment_type_not_found")
    return AttachmentTypeRead.model_validate(row)


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
        options=[
            selectinload(Applicant.type_money_category),
            selectinload(Applicant.bank_name),
        ],
    )
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    if "type_money_category_id" in payload:
        old_category_id = applicant.type_money_category_id
        old_started_at = applicant.process_started_at
        tmc_id = payload["type_money_category_id"]
        if tmc_id is not None:
            tmc_row = await _get_row(session, TypeMoneyCategory, tmc_id)
            if tmc_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="type_money_category_not_found",
                )
        else:
            tmc_row = None
        applicant.type_money_category_id = tmc_id

        bank_code = applicant.bank_name.bank_code if applicant.bank_name else None
        category_acronym = tmc_row.name_acronym if tmc_row is not None else None
        start_process = old_started_at is None and tmc_id is not None
        category_changed = tmc_id != old_category_id
        recalc_sla_only = old_started_at is not None and (
            category_changed or tmc_id is None
        )
        if start_process or recalc_sla_only:
            apply_process_sla_to_applicant(
                applicant,
                category_acronym=category_acronym,
                bank_code=bank_code,
                start_process=start_process,
                recalc_sla_only=recalc_sla_only,
            )
        apply_emergency_flag_for_money_category(applicant, category_acronym)

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
        is_emergency=applicant.is_emergency,
        updated_at=applicant.updated_at,
        **process_sla_fields_dict(applicant.process_started_at, applicant.process_sla_days),
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
        "ประเภทคำร้อง (แต่ละรายการมี `request_other_text`, `money_amount` จากหน้า 11 / case_regulation_choice), "
        "ประวัติสวัสดิการ, สถานะ, หลักฐานพร้อม path สำหรับ GET รูป"
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
    "/welfare-dda-ref",
    response_model=WelfareDdaRefBundleRead,
    status_code=status.HTTP_201_CREATED,
    summary="สร้าง welfare_dda_ref และ welfare_payment หลายรายการ",
    description=(
        "บันทึกหมายเลข dda_ref หนึ่งรายการ พร้อม welfare_payment ต่อ applicant ใน dda_ref_detail — "
        "payment_number, payment_038_reason, transaction_date, effective_date, user_sdshv, is_037_or_038 บน payment ว่าง (null) ไว้สำหรับกระบวนการอัปเดตภายหลัง"
    ),
)
async def create_welfare_dda_ref_bundle(
    body: WelfareDdaRefBundleCreate,
    session: AsyncSession = Depends(get_session),
) -> WelfareDdaRefBundleRead:
    dda_ref = body.dda_ref.strip()
    if not dda_ref:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="dda_ref_required")

    applicant_ids = [item.applicant_id for item in body.dda_ref_detail]
    if len(applicant_ids) != len(set(applicant_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="duplicate_applicant_id_in_dda_ref_detail",
        )

    found_ids = set(
        await session.scalars(select(Applicant.id).where(Applicant.id.in_(applicant_ids)))
    )
    missing = sorted(set(applicant_ids) - found_ids)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"applicant_not_found": missing},
        )

    dda_row = WelfareDdaRef(dda_ref=dda_ref, user_sdshv=body.user_sdshv)
    session.add(dda_row)
    await session.flush()

    for item in body.dda_ref_detail:
        session.add(
            WelfarePayment(
                applicant_id=item.applicant_id,
                dda_ref_id=dda_row.id,
                is_037_or_038=None,
                payment_number=None,
                payment_038_reason=None,
                user_sdshv=None,
                transaction_date=None,
                effective_date=None,
            ),
        )

    await session.commit()

    result = await session.execute(
        select(WelfareDdaRef)
        .options(selectinload(WelfareDdaRef.welfare_payments))
        .where(WelfareDdaRef.id == dda_row.id),
    )
    dda_row = result.scalar_one()
    return WelfareDdaRefBundleRead(
        id=dda_row.id,
        dda_ref=dda_row.dda_ref,
        user_sdshv=dda_row.user_sdshv,
        welfare_payments=[
            WelfarePaymentInitialRead.model_validate(p)
            for p in sorted(dda_row.welfare_payments, key=lambda x: x.id)
        ],
    )


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


@router.get(
    "/review-fields",
    response_model=list[ReviewFieldRead],
    summary="รายการหัวข้อที่สามารถส่งกลับแก้ไขได้",
)
async def list_review_fields(
    session: AsyncSession = Depends(get_session),
) -> list[ReviewFieldRead]:
    result = await session.execute(
        select(ReviewField)
        .where(ReviewField.is_active.is_(True))
        .order_by(ReviewField.step.asc(), ReviewField.display_order.asc()),
    )
    return [ReviewFieldRead.model_validate(row) for row in result.scalars().all()]


@router.get(
    "/welfare-edit-request",
    summary="ดึง review comments ล่าสุดของ applicant (status=8)",
)
async def get_welfare_edit_request(
    applicant_id: int = Query(..., ge=1),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    result = await session.execute(
        select(WelfareRequestStatus)
        .where(
            WelfareRequestStatus.applicant_id == applicant_id,
            WelfareRequestStatus.current_status_id == 8,
        )
        .order_by(WelfareRequestStatus.id.desc())
        .limit(1)
        .options(
            selectinload(WelfareRequestStatus.review_comments).selectinload(
                WelfareReviewComment.review_field
            )
        ),
    )
    status_row = result.scalar_one_or_none()
    if not status_row:
        return []
    return [
        {
            "review_field_id": c.review_field_id,
            "name": c.review_field.name,
            "label": c.review_field.label,
            "step": c.review_field.step,
            "reason": c.reason,
        }
        for c in status_row.review_comments
    ]


@router.post(
    "/welfare-edit-request",
    response_model=WelfareEditRequestRead,
    status_code=status.HTTP_201_CREATED,
    summary="ส่งคำขอแก้ไขข้อมูล — เปลี่ยนสถานะเป็น 8 + บันทึก comment ต่อหัวข้อ (atomic)",
)
async def create_welfare_edit_request(
    body: WelfareEditRequestCreate,
    session: AsyncSession = Depends(get_session),
) -> WelfareEditRequestRead:
    applicant = await session.get(Applicant, body.applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    _EDIT_REQUEST_STATUS_ID = 8
    if await _get_row(session, CurrentStatus, _EDIT_REQUEST_STATUS_ID) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="current_status_not_found")

    status_log = WelfareRequestStatus(
        applicant_id=body.applicant_id,
        current_status_id=_EDIT_REQUEST_STATUS_ID,
        remarks=body.remarks or "",
        update_by_sdshv=body.update_by_sdshv,
    )
    session.add(status_log)
    await session.flush()

    comments: list[WelfareReviewComment] = []
    for item in body.comments:
        if await _get_row(session, ReviewField, item.review_field_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"review_field_not_found:{item.review_field_id}",
            )
        comment = WelfareReviewComment(
            welfare_request_status_id=status_log.id,
            review_field_id=item.review_field_id,
            reason=item.reason,
        )
        session.add(comment)
        comments.append(comment)

    await session.commit()

    return WelfareEditRequestRead(
        welfare_request_status_id=status_log.id,
        comments=[
            WelfareReviewCommentRead.model_validate(c) for c in comments
        ],
    )

