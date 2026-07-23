"""ชุด API สำหรับรายการคำร้องฝั่งเจ้าหน้าที่."""

from __future__ import annotations

from datetime import date, datetime
import uuid

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, case, false, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from uuid import UUID

from ...services.esignature_storage import load_esignature_base64 as _load_esignature_base64
from ...services.article_approval import (
    get_article_by_applicant_id,
    record_approve_case_with_status,
    resolve_active_pmj_rejects_for_applicant,
    resolve_article_id_for_applicant,
    upsert_article,
)
from ...api.v1.cases import _load_full_applicant, applicant_to_case_read
from ...core.database import get_session
from ...core.file_validation import assert_image_magic_bytes
from ...models.address import Address
from ...models.applicant import Applicant
from ...models.applicant_submission_audit import ApplicantSubmissionAudit
from ...models.geo import District, Postcode, Province, SubDistrict, SubDistrictPostcode
from ...models.lookup import AttachmentType, BankName, CurrentStatus, TypeMoneyCategory
from ...models.economic import HouseholdMember
from ...models.person import Person
from ...models.status_log import WelfareRequestStatus
from ...models.intake import CaseHandling, CaseRegulationChoice
from ...models.mso_send import MoreMso, SendData, TypeSend
from ...models.payment import ApproveCase, FilePayment, WelfareDdaRef, WelfarePayment
from ...models.welfare import WelfareEvidence
from ...services.process_sla import (
    apply_emergency_flag_for_money_category,
    apply_process_sla_to_applicant,
    maybe_freeze_process_sla_for_status,
    process_sla_fields_dict,
)
from ...constants.current_status import (
    CURRENT_STATUS_EDIT_REQUESTED,
    CURRENT_STATUS_PENDING_INTAKE,
    CURRENT_STATUS_RECEIVED,
    CURRENT_STATUS_WITHDRAWING,
    CURRENT_STATUS_WITHDRAWING_APPROVED,
    CURRENT_STATUS_MSO_FORWARDED,
    PAYMENT_EDIT_PRESERVE_STATUS_IDS,
    STAFF_CASE_SECTION_EDIT_STATUS_IDS,
)
from ...services.case_update import apply_case_update
from ...services.staff_edit_audit import (
    EVENT_TYPE_SECTION_EDIT,
    EVENT_TYPE_SURVEY_EDIT,
    build_staff_section_edit_remarks,
    build_staff_section_edit_sections,
    build_staff_survey_edit_remarks,
    record_staff_data_edit_audit,
)
from ...schemas.case_welfare import WelfareApplicantUpdate, WelfareCaseUpdate, WelfareEvidenceUploadRead
from ...models.review import WelfareReviewComment
from ...services.file_payment_upload import (
    ATTACHMENT_PDF_037_ID,
    file_payment_upload_root,
    save_file_payment_pdf,
)
from ...services.payment_round_metrics import (
    applicant_payment_metrics,
    load_payments_by_applicant_ids,
)
from ...services.payment_upload_history import build_payment_upload_history
from ...services.staff_digest_summary import fetch_staff_digest_summary
from ...services.self_submit_fiscal_siblings import load_fiscal_year_self_submit_enrichment
from ...services.ktb_audit_read import enrich_case_for_staff_ktb_defaults, ktb_audit_api_fields
from ...services.dwf_scope import (
    SOR_KOR_TYPE_MONEY_ID,
    allowed_sor_kor_province_ids,
    division_name_for_id,
    group_for_province,
    is_dwf_mother_province,
    visible_cover_document_batch_province_ids,
    visible_finance_sor_kor_province_ids,
)
from ...services.citizen_status_email_policy import (
    CitizenStatusEmailTrigger,
    fetch_latest_status_id,
    fetch_previous_status_id,
    is_status_advancement,
)
from ...services.status_email_notification import (
    enqueue_case_submitted_email,
    enqueue_payment_037_upload_email,
    enqueue_status_email,
)
from ...services.welfare_evidence import validate_welfare_evidence_upload


def _staff_evidence_view_path(applicant_id: int, evidence_id: int) -> str:
    return f"/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}/file"
from ...services.welfare_payment_flow import (
    apply_037_update,
    apply_038_update,
    apply_fields_on_active_dda,
    apply_payment_update_by_id,
    file_payment_owned_by_applicant,
    is_payment_round_status_correction,
    resolve_payment_round_target_status,
)
from ...settings import resolved_upload_root, settings
from ...schemas.address import AddressRead
from ...schemas.article import ArticleCreate, ArticleRead, ArticleUpdate
from ...schemas.cover_document_batch import (
    CoverDocumentBatchCreate,
    CoverDocumentBatchListResponse,
    CoverDocumentBatchRead,
    CoverDocumentBatchUpdate,
)
from ...services.cover_document_batch import (
    batch_to_read,
    create_cover_document_batch,
    get_cover_document_batch,
    list_cover_document_batches,
    update_cover_document_batch,
)
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
    WelfarePaymentBatchUpdate,
    WelfarePaymentBatchRead,
)
from ...schemas.case_for_staff import (
    CaseForStaffApplicantStaffFieldsRead,
    CaseForStaffApplicantStaffFieldsUpdate,
    CaseForStaffResponsibleDivisionRead,
    CaseForStaffResponsibleDivisionUpdate,
    StaffCaseSectionsUpdate,
    StaffDataEditLogCreate,
    CaseForStaffFinanceListResponse,
    CaseForStaffFinanceRead,
    CaseForStaffListResponse,
    CaseForStaffStatusSummaryResponse,
    CaseForStaffPorKor1DetailResponse,
    CaseForStaffRead,
    CaseForStaffWelfareRequestStatusCreate,
    MoreMsoRead,
    MoreMsoUpsert,
    PorKor1AddressItem,
    PorKor1ApplicantSection,
    PorKor1DependencyItem,
    PorKor1EconomicItem,
    PorKor1EvidenceItem,
    PorKor1MemberEvidenceItem,
    PorKor1HouseholdMemberItem,
    PorKor1PersonSection,
    PorKor1Summary,
    PorKor1TypeMoney,
    PorKor1WelfareHistoryDetailRead,
    PorKor1WelfareHistoryRead,
    PorKor1WelfareRequestStatusSection,
    PorKor1WelfareRequestTypeItem,
    PorKor1ReturnEditSection,
    ReturnEditCommentItem,
    MsoForwardCreate,
    MsoForwardRead,
    MsoForwardStatusRead,
    SendDataCreate,
    SendDataRead,
    TypeSendRead,
)
from ...constants.type_send import TYPE_SEND_ID_TO_CHANNEL
from ...services.mso_forward import fetch_mso_forward_status, record_mso_forward
from ...schemas.case_welfare import WelfareCaseRead
from ...schemas.dependency import DependencyLoadRead
from ...schemas.economic import EconomicInfoRead, HouseholdMemberRead
from ...schemas.lookup import AttachmentTypeRead, CurrentStatusRead, TypeMoneyCategoryRead
from ...schemas.person import PersonRead
from ...models.review import ReviewField, WelfareReviewComment
from ...schemas.review import (
    ReviewFieldRead,
    WelfareEditRequestCreate,
    WelfareEditRequestRead,
    WelfareReviewCommentRead,
)
from ...schemas.case_data_edit_log import CaseDataEditLogRead
from ...schemas.status_log import WelfareRequestStatusRead
from ...schemas.welfare import (
    WelfareEvidenceRead,
    WelfareHistoryDetailRead,
    WelfareRequestTypeRead,
)


from ...core.staff_security import StaffClaims, require_staff

router = APIRouter(
    prefix="/v1/case_for_staff",
    tags=["case_for_staff"],
    dependencies=[Depends(require_staff)],
)

ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _person_age_from_birth_date(birth_date: date) -> int:
    """อายุเต็มปี ณ วันนี้ — ลด 1 ปีถ้ายังไม่ถึงวันเกิดในปีปัจจุบัน."""
    today = date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return max(age, 0)


def _process_sla_fields_from_applicant(applicant: Applicant) -> dict[str, object]:
    completed_at = applicant.process_completed_at
    return process_sla_fields_dict(
        applicant.process_started_at,
        applicant.process_sla_days,
        completed_at=completed_at,
        frozen_elapsed=applicant.time_count_process if completed_at is not None else None,
    )


def _enrich_row_process_sla(data: dict[str, object]) -> None:
    completed_at = data.get("process_completed_at")  # type: ignore[arg-type]
    frozen = data.get("time_count_process") if completed_at is not None else None
    data.update(
        process_sla_fields_dict(
            data.get("process_started_at"),  # type: ignore[arg-type]
            data.get("process_sla_days"),  # type: ignore[arg-type]
            completed_at=completed_at,
            frozen_elapsed=frozen if isinstance(frozen, int) else None,  # type: ignore[arg-type]
        ),
    )


def _enrich_case_for_staff_row(data: dict[str, object]) -> None:
    birth_date = data.pop("birth_date", None)
    if birth_date is not None:
        data["person_age"] = _person_age_from_birth_date(birth_date)  # type: ignore[arg-type]
    data.pop("persons_id", None)
    data.pop("requester_relation_id", None)
    data.setdefault("prior_self_submit_case_numbers", [])
    data.setdefault("self_submit_fiscal_year_count", 0)
    data.setdefault("self_submit_fiscal_year_case_numbers", [])
    enrich_case_for_staff_ktb_defaults(data)
    _enrich_row_process_sla(data)
    has_return_edit_resubmitted = data.pop("has_return_edit_resubmitted", None)
    if has_return_edit_resubmitted is not None:
        data["is_return_edit_resubmitted"] = bool(has_return_edit_resubmitted)
        return

    current = data.get("current_status_id")
    previous = data.get("previous_status_id")
    data["is_return_edit_resubmitted"] = (
        current == CURRENT_STATUS_PENDING_INTAKE and previous == CURRENT_STATUS_EDIT_REQUESTED
    )


def _row_to_case_for_staff_read(row: object) -> CaseForStaffRead:
    data = dict(row)  # type: ignore[arg-type]
    _enrich_case_for_staff_row(data)
    return CaseForStaffRead.model_validate(data)


def _row_to_case_for_staff_finance_read(row: object) -> CaseForStaffFinanceRead:
    data = dict(row)  # type: ignore[arg-type]
    _enrich_case_for_staff_row(data)
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

    latest_status_id = (
        case.latest_welfare_request_status.current_status_id
        if case.latest_welfare_request_status is not None
        else None
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
        responsible_division_id=(
            orm.case_handling.responsible_division_id if orm.case_handling else None
        ),
        can_edit_case_sections=(
            latest_status_id in STAFF_CASE_SECTION_EDIT_STATUS_IDS
            if latest_status_id is not None
            else False
        ),
        **_process_sla_fields_from_applicant(orm),
        **ktb_audit_api_fields(orm),
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
            occupation_type_name=e.occupation_type.name if e.occupation_type else None,
            family_occupation_type_name=e.family_occupation_type.name if e.family_occupation_type else None,
        )
        for e in sorted(orm.economic_infos, key=lambda x: x.id)
    ]

    # สร้าง lookup: household_member_id → รายการ evidences ของสมาชิกคนนั้น
    member_evidence_map: dict[int, list[PorKor1MemberEvidenceItem]] = {}
    for ev in orm.welfare_evidences:
        if ev.household_member_id is None:
            continue
        mid = ev.household_member_id
        if mid not in member_evidence_map:
            member_evidence_map[mid] = []
        member_evidence_map[mid].append(
            PorKor1MemberEvidenceItem(
                evidence_id=ev.id,
                attachment_type_id=ev.attachment_type_id,
                attachment_type_name=ev.attachment_type.name if ev.attachment_type else None,
                file_other_type_name=ev.file_other_type_name,
                view_path=_staff_evidence_view_path(orm.id, ev.id),
            )
        )

    household_members: list[PorKor1HouseholdMemberItem] = []
    for m in sorted(orm.household_members, key=lambda x: x.seq):
        item = PorKor1HouseholdMemberItem.model_validate(m)
        item.member_evidences = member_evidence_map.get(m.id, [])
        household_members.append(item)

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

    # ดึง return-edit comments จาก status 8 ล่าสุด
    edit_logs = [
        log for log in orm.status_logs
        if log.current_status_id == CURRENT_STATUS_EDIT_REQUESTED
    ]
    latest_edit_log = (
        sorted(edit_logs, key=lambda s: (s.updated_at, s.id), reverse=True)[0]
        if edit_logs else None
    )
    return_edit: PorKor1ReturnEditSection | None = None
    if latest_edit_log is not None and latest_edit_log.review_comments:
        comments = [
            ReturnEditCommentItem(
                review_field_id=c.review_field_id,
                label=c.review_field.label if c.review_field else str(c.review_field_id),
                step=c.review_field.step if c.review_field else 0,
                reason=c.reason,
            )
            for c in sorted(
                latest_edit_log.review_comments,
                key=lambda x: (
                    x.review_field.step if x.review_field else 0,
                    x.review_field.display_order if x.review_field else 0,
                ),
            )
        ]
        return_edit = PorKor1ReturnEditSection(
            comments=comments,
            remarks=latest_edit_log.remarks,
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

    # กรองเฉพาะ evidence ของผู้ยื่น (household_member_id IS NULL)
    # evidence ของสมาชิกในครัวเรือนแยกใช้ endpoint /v1/cases/{id}/evidences?household_member_id=...
    evidences = [
        PorKor1EvidenceItem(
            evidence=WelfareEvidenceRead.model_validate(ev),
            attachment_type_name=ev.attachment_type.name if ev.attachment_type else None,
            view_path=_staff_evidence_view_path(orm.id, ev.id),
        )
        for ev in sorted(orm.welfare_evidences, key=lambda x: x.id)
        if ev.household_member_id is None
    ]

    data_edit_logs = [
        CaseDataEditLogRead.model_validate(log)
        for log in sorted(orm.data_edit_logs, key=lambda x: (x.created_at, x.id), reverse=True)
    ]

    return CaseForStaffPorKor1DetailResponse(
        summary=summary,
        person=person_section,
        applicant=applicant_section,
        addresses=addresses,
        dependency_loads=dependency_loads,
        economic_infos=economic_infos,
        household_members=household_members,
        welfare_request_types=welfare_request_types,
        welfare_history=welfare_history_section,
        welfare_request_status=welfare_request_status,
        evidences=evidences,
        return_edit=return_edit,
        data_edit_logs=data_edit_logs,
    )


def _clean_text_filter(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _parse_int_query_values(values: list[str] | None) -> list[int] | None:
    if not values:
        return None
    parsed: list[int] = []
    for value in values:
        for part in str(value).split(","):
            part = part.strip()
            if not part:
                continue
            if not part.isdigit():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="invalid_integer_query_value",
                )
            parsed.append(int(part))
    return parsed or None


def _actor_province_id(staff: StaffClaims, province_id: int) -> int:
    return province_id if staff.is_internal else staff.province_id


def _validated_requested_dwf_province_ids(
    actor_province_id: int,
    requested_province_ids: list[int] | None,
) -> tuple[int, ...]:
    allowed = allowed_sor_kor_province_ids(actor_province_id)
    if not requested_province_ids:
        return allowed
    requested = tuple(dict.fromkeys(requested_province_ids))
    invalid = [pid for pid in requested if pid not in allowed]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="province_ids_outside_dwf_scope",
        )
    return requested


def _case_location_visibility_condition(
    *,
    province_id: int,
    staff: StaffClaims,
    dwf_scope: bool,
    requested_province_ids: list[int] | None,
    type_money_ids: set[int] | None,
    province_column,
    type_money_column,
):
    actor_province_id = _actor_province_id(staff, province_id)
    auto_expand_sor_kor = (
        type_money_ids == {SOR_KOR_TYPE_MONEY_ID}
        and is_dwf_mother_province(actor_province_id)
    )
    if not dwf_scope:
        if auto_expand_sor_kor:
            # Sor Kor list visibility expands automatically for configured mother provinces.
            sor_kor_province_ids = _validated_requested_dwf_province_ids(
                actor_province_id,
                requested_province_ids,
            )
            return province_column.in_(sor_kor_province_ids)
        if requested_province_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="province_ids_requires_dwf_scope",
            )
        return province_column == province_id

    group = group_for_province(actor_province_id)
    if group is None:
        if requested_province_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="province_ids_outside_dwf_scope",
            )
        return province_column == province_id

    sor_kor_province_ids = _validated_requested_dwf_province_ids(
        actor_province_id,
        requested_province_ids,
    )
    if type_money_ids is not None and SOR_KOR_TYPE_MONEY_ID not in type_money_ids:
        return province_column == province_id
    if type_money_ids == {SOR_KOR_TYPE_MONEY_ID}:
        return province_column.in_(sor_kor_province_ids)
    return or_(
        and_(
            type_money_column == SOR_KOR_TYPE_MONEY_ID,
            province_column.in_(sor_kor_province_ids),
        ),
        and_(
            or_(
                type_money_column.is_(None),
                type_money_column != SOR_KOR_TYPE_MONEY_ID,
            ),
            province_column == province_id,
        ),
    )


def _finance_location_visibility_condition(
    *,
    province_id: int,
    staff: StaffClaims,
    dwf_scope: bool,
    requested_province_ids: list[int] | None,
    type_money_ids: set[int] | None,
    province_column,
    type_money_column,
):
    actor_province_id = _actor_province_id(staff, province_id)
    if is_dwf_mother_province(actor_province_id):
        province_ids = _validated_requested_dwf_province_ids(
            actor_province_id,
            requested_province_ids,
        )
        return province_column.in_(province_ids)

    finance_sor_kor_province_ids = visible_finance_sor_kor_province_ids(actor_province_id)
    if not finance_sor_kor_province_ids and SOR_KOR_TYPE_MONEY_ID in (
        type_money_ids or {SOR_KOR_TYPE_MONEY_ID}
    ):
        # DWF child provinces have no Sor Kor finance visibility, even for their own province.
        if type_money_ids == {SOR_KOR_TYPE_MONEY_ID}:
            return false()
        return and_(
            province_column == province_id,
            or_(
                type_money_column.is_(None),
                type_money_column != SOR_KOR_TYPE_MONEY_ID,
            ),
        )

    return _case_location_visibility_condition(
        province_id=province_id,
        staff=staff,
        dwf_scope=dwf_scope,
        requested_province_ids=requested_province_ids,
        type_money_ids=type_money_ids,
        province_column=province_column,
        type_money_column=type_money_column,
    )


async def _applicant_current_address_province_id(
    session: AsyncSession,
    applicant_id: int,
) -> int | None:
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
    return await session.scalar(
        select(District.province_id)
        .select_from(Applicant)
        .join(Person, Person.id == Applicant.persons_id)
        .outerjoin(
            primary_address_sq,
            and_(
                primary_address_sq.c.applicant_id == Applicant.id,
                primary_address_sq.c.rn == 1,
            ),
        )
        .join(SubDistrictPostcode, SubDistrictPostcode.id == location_subdistrict_postcode_id)
        .join(SubDistrict, SubDistrict.id == SubDistrictPostcode.sub_district_id)
        .join(District, District.id == SubDistrict.district_id)
        .where(Applicant.id == applicant_id)
        .limit(1)
    )


async def _assert_dwf_status_change_allowed(
    session: AsyncSession,
    *,
    staff: StaffClaims,
    applicant: Applicant,
    target_status_id: int,
) -> None:
    if staff.is_internal:
        return
    if target_status_id != CURRENT_STATUS_RECEIVED:
        return
    if applicant.type_money_category_id != SOR_KOR_TYPE_MONEY_ID:
        return

    actor_province_id = staff.province_id
    group = group_for_province(actor_province_id)
    if group is None:
        return

    current_address_province_id = await _applicant_current_address_province_id(
        session,
        applicant.id,
    )
    if current_address_province_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="applicant_current_address_province_not_found",
        )

    if not is_dwf_mother_province(actor_province_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="dwf_child_cannot_accept_sor_kor_status_2",
        )

    if current_address_province_id not in allowed_sor_kor_province_ids(actor_province_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="applicant_outside_dwf_scope",
        )


def _cover_document_batch_is_visible_to_staff(
    batch,
    staff: StaffClaims,
) -> bool:
    if staff.is_internal:
        return True
    # Cover-document actions keep the PMJ workflow rule: Sor Kor mother provinces can act for children.
    return batch.province_id in visible_cover_document_batch_province_ids(
        staff.province_id,
        batch.type_money_id,
    )


def _assert_cover_document_batch_visible_to_staff(
    batch,
    staff: StaffClaims,
) -> None:
    if not _cover_document_batch_is_visible_to_staff(batch, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="cover_document_batch_outside_scope",
        )


def _merge_payment_metrics_into_rows(
    rows: list,
    payments_by_applicant: dict[int, list[WelfarePayment]],
) -> list[dict]:
    merged: list[dict] = []
    for row in rows:
        data = dict(row)
        data["current_address_province_id"] = data.get("province_id")
        data["current_address_province_name"] = data.get("province_name")
        data["responsible_division_name"] = division_name_for_id(
            data.get("responsible_division_id")  # type: ignore[arg-type]
        )
        metrics = applicant_payment_metrics(
            payments_by_applicant.get(data["applicant_id"], []),
        )
        data.update(metrics)
        merged.append(data)
    return merged


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


async def _apply_payment_status_if_needed(
    session: AsyncSession,
    applicant_id: int,
    payment: WelfarePayment,
    updates: dict,
) -> tuple[WelfareRequestStatus | None, CurrentStatus | None]:
    """ตั้งสถานะ 10 เมื่อรอบ 037-only; สถานะ 3 เมื่อมีทั้ง 037 และ 038 ในรอบเดียวกัน."""
    if payment.is_037_or_038 is None:
        return None, None

    latest_status_id = await fetch_latest_status_id(session, applicant_id=applicant_id)

    batch_id = updates.get("upload_batch_id")
    if batch_id is None:
        batch_id = payment.upload_batch_id

    target_status_id = await resolve_payment_round_target_status(
        session,
        applicant_id,
        payment.dda_ref_id,
        payment_id=payment.id,
        upload_batch_id=batch_id,
    )
    if target_status_id is None:
        return None, None

    is_correction = is_payment_round_status_correction(latest_status_id, target_status_id)

    if latest_status_id in PAYMENT_EDIT_PRESERVE_STATUS_IDS and not is_correction:
        return None, None

    if latest_status_id == target_status_id:
        return None, None

    if not is_status_advancement(latest_status_id, target_status_id) and not is_correction:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="status_cannot_go_backward",
        )

    status_row = await _get_row(session, CurrentStatus, target_status_id)
    if status_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="current_status_not_found")

    remarks = (
        "บันทึกผลจ่ายเงิน 037/038"
        if target_status_id == CURRENT_STATUS_WITHDRAWING_APPROVED
        else "บันทึกผลจ่ายเงิน 037"
    )

    status_log = WelfareRequestStatus(
        applicant_id=applicant_id,
        current_status_id=target_status_id,
        remarks=remarks,
        update_by_sdshv=updates.get("user_sdshv"),
    )
    session.add(status_log)
    if target_status_id == CURRENT_STATUS_WITHDRAWING:
        applicant = await session.get(Applicant, applicant_id)
        if applicant is not None:
            maybe_freeze_process_sla_for_status(applicant, target_status_id)
    return status_log, status_row


@router.get("", response_model=CaseForStaffListResponse)
async def list_cases_for_staff(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการค้นหา"),
    province_ids: list[str] | None = Query(
        None,
        description="DWF scope narrowing only; values must belong to the DWF group resolved from province_id/staff",
    ),
    dwf_scope: bool = Query(False, description="Use DWF/Sor Kor visibility from drpod_dwf.json"),
    case_number: str | None = Query(None, description="ค้นหาจากเลข case"),
    current_status: str | None = Query(None, description="ค้นหาจากข้อความสถานะฝั่งเจ้าหน้าที่"),
    current_status_id: list[int] | None = Query(
        None,
        description="Filter by current_status_id; supports repeated query values",
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
    type_money_id: int | None = Query(None, description="กรองตาม type_money_category.id (applicants.type_money_category_id)"),
    session: AsyncSession = Depends(get_session),
    staff: StaffClaims = Depends(require_staff),
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

    prev_status_sq = (
        select(
            WelfareRequestStatus.applicant_id.label("applicant_id"),
            WelfareRequestStatus.current_status_id.label("previous_status_id"),
            func.row_number()
            .over(
                partition_by=WelfareRequestStatus.applicant_id,
                order_by=[WelfareRequestStatus.updated_at.desc(), WelfareRequestStatus.id.desc()],
            )
            .label("rn"),
        )
        .subquery()
    )

    return_edit_status = aliased(WelfareRequestStatus)
    return_edit_resubmit_status = aliased(WelfareRequestStatus)
    return_edit_resubmitted_sq = (
        select(return_edit_status.applicant_id.label("applicant_id"))
        .select_from(return_edit_status)
        .join(
            return_edit_resubmit_status,
            and_(
                return_edit_resubmit_status.applicant_id == return_edit_status.applicant_id,
                return_edit_resubmit_status.current_status_id == CURRENT_STATUS_PENDING_INTAKE,
                or_(
                    return_edit_resubmit_status.updated_at > return_edit_status.updated_at,
                    and_(
                        return_edit_resubmit_status.updated_at == return_edit_status.updated_at,
                        return_edit_resubmit_status.id > return_edit_status.id,
                    ),
                ),
            ),
        )
        .where(return_edit_status.current_status_id == CURRENT_STATUS_EDIT_REQUESTED)
        .group_by(return_edit_status.applicant_id)
        .subquery()
    )

    active_pmj_reject_sq = (
        select(
            ApproveCase.applicant_id.label("applicant_id"),
            ApproveCase.reject_reason.label("pmj_reject_reason"),
            func.row_number()
            .over(
                partition_by=ApproveCase.applicant_id,
                order_by=ApproveCase.id.desc(),
            )
            .label("rn"),
        )
        .where(
            ApproveCase.approve_status.is_(False),
            ApproveCase.reject_reason.is_not(None),
            ApproveCase.reject_resolved_at.is_(None),
        )
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
            Person.birth_date.label("birth_date"),
            Applicant.created_at.label("datetime_create"),
            Applicant.persons_id.label("persons_id"),
            Applicant.requester_relation_id.label("requester_relation_id"),
            Applicant.is_emergency.label("is_emergency"),
            Applicant.is_existing_case.label("is_existing_case"),
            Applicant.process_started_at.label("process_started_at"),
            Applicant.process_sla_days.label("process_sla_days"),
            Applicant.process_completed_at.label("process_completed_at"),
            Province.id.label("province_id"),
            Province.name.label("province_name"),
            District.id.label("district_id"),
            District.name.label("district_name"),
            SubDistrict.id.label("subdistrict_id"),
            SubDistrict.name.label("subdistrict_name"),
            SubDistrictPostcode.id.label("subdistrict_postcode_id"),
            Postcode.name.label("postcode"),
            have_dda_ref.label("have_dda_ref"),
            is_approved.label("is_approved"),
            prev_status_sq.c.previous_status_id.label("previous_status_id"),
            case(
                (return_edit_resubmitted_sq.c.applicant_id.is_not(None), True),
                else_=False,
            ).label("has_return_edit_resubmitted"),
            case(
                (
                    and_(
                        active_pmj_reject_sq.c.applicant_id.is_not(None),
                        ~is_approved,
                    ),
                    True,
                ),
                else_=False,
            ).label("is_pmj_rejected"),
            case(
                (
                    and_(
                        active_pmj_reject_sq.c.applicant_id.is_not(None),
                        ~is_approved,
                    ),
                    active_pmj_reject_sq.c.pmj_reject_reason,
                ),
                else_=None,
            ).label("pmj_reject_reason"),
            ApplicantSubmissionAudit.require_ktb_corporate.label("require_ktb_corporate"),
            ApplicantSubmissionAudit.require_ktb_reason.label("require_ktb_reason"),
            ApplicantSubmissionAudit.existing_case_source.label("existing_case_source"),
            ApplicantSubmissionAudit.existing_case_detected_sources.label(
                "existing_case_detected_sources",
            ),
            ApplicantSubmissionAudit.existing_case_ref_id.label("existing_case_ref_id"),
            ApplicantSubmissionAudit.existing_case_province_id.label("existing_case_province_id"),
            ApplicantSubmissionAudit.existing_case_province_name.label("existing_case_province_name"),
            ApplicantSubmissionAudit.submission_province_id.label("submission_province_id"),
            ApplicantSubmissionAudit.submission_province_name.label("submission_province_name"),
            ApplicantSubmissionAudit.is_account_changed.label("is_account_changed"),
            CaseHandling.responsible_division_id.label("responsible_division_id"),
        )
        .join(Person, Person.id == Applicant.persons_id)
        .outerjoin(CaseHandling, CaseHandling.applicant_id == Applicant.id)
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
        .outerjoin(
            prev_status_sq,
            and_(
                prev_status_sq.c.applicant_id == Applicant.id,
                prev_status_sq.c.rn == 2,
            ),
        )
        .outerjoin(
            return_edit_resubmitted_sq,
            return_edit_resubmitted_sq.c.applicant_id == Applicant.id,
        )
        .outerjoin(
            active_pmj_reject_sq,
            and_(
                active_pmj_reject_sq.c.applicant_id == Applicant.id,
                active_pmj_reject_sq.c.rn == 1,
            ),
        )
        .outerjoin(
            ApplicantSubmissionAudit,
            ApplicantSubmissionAudit.applicant_id == Applicant.id,
        )
        .outerjoin(TypeMoneyCategory, TypeMoneyCategory.id == Applicant.type_money_category_id)
        .where(
            _case_location_visibility_condition(
                province_id=province_id,
                staff=staff,
                dwf_scope=dwf_scope,
                requested_province_ids=_parse_int_query_values(province_ids),
                type_money_ids={type_money_id} if type_money_id is not None else None,
                province_column=Province.id,
                type_money_column=Applicant.type_money_category_id,
            )
        )
        .order_by(Applicant.created_at.desc(), Applicant.id.desc())
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
    if type_money_id is not None:
        stmt = stmt.where(Applicant.type_money_category_id == type_money_id)

    filtered_count_stmt = select(func.count()).select_from(
        stmt.with_only_columns(Applicant.id).order_by(None).distinct().subquery()
    )

    total_applicants = await session.scalar(total_stmt)
    filtered_applicants = await session.scalar(filtered_count_stmt)
    result = await session.execute(stmt)
    rows = result.mappings().all()
    applicant_ids = [row["applicant_id"] for row in rows]
    payments_by_applicant = await load_payments_by_applicant_ids(session, applicant_ids)
    enriched_rows = _merge_payment_metrics_into_rows(rows, payments_by_applicant)
    fiscal_enrichment = await load_fiscal_year_self_submit_enrichment(session, enriched_rows)
    for row in enriched_rows:
        applicant_id = row["applicant_id"]
        row["prior_self_submit_case_numbers"] = fiscal_enrichment.prior_case_numbers.get(
            applicant_id,
            [],
        )
        row["self_submit_fiscal_year_count"] = fiscal_enrichment.fiscal_year_count.get(
            applicant_id,
            0,
        )
        row["self_submit_fiscal_year_case_numbers"] = fiscal_enrichment.fiscal_year_case_numbers.get(
            applicant_id,
            [],
        )
    return CaseForStaffListResponse(
        province_id=province.id,
        province_name=province.name,
        total_applicants=total_applicants or 0,
        filtered_applicants=filtered_applicants or 0,
        items=[_row_to_case_for_staff_read(row) for row in enriched_rows],
    )


async def _list_cases_for_staff_finance_impl(
    session: AsyncSession,
    province_id: int,
    province_ids: list[str] | None,
    dwf_scope: bool,
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
    staff: StaffClaims,
    auto_expand_mother_province: bool = False,
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
            Person.birth_date.label("birth_date"),
            Applicant.created_at.label("datetime_create"),
            Applicant.is_emergency.label("is_emergency"),
            Applicant.is_existing_case.label("is_existing_case"),
            Applicant.process_started_at.label("process_started_at"),
            Applicant.process_sla_days.label("process_sla_days"),
            Applicant.process_completed_at.label("process_completed_at"),
            Province.id.label("province_id"),
            Province.name.label("province_name"),
            District.id.label("district_id"),
            District.name.label("district_name"),
            SubDistrict.id.label("subdistrict_id"),
            SubDistrict.name.label("subdistrict_name"),
            SubDistrictPostcode.id.label("subdistrict_postcode_id"),
            Postcode.name.label("postcode"),
            latest_dda_sq.c.dda_ref.label("dda_ref"),
            welfare_payment_with_dda_exists.label("have_dda_ref"),
            is_approved.label("is_approved"),
            Applicant.bank_name_id.label("bank_name_id"),
            BankName.bank_code.label("bank_code"),
            Applicant.bank_account_no.label("bank_account_no"),
            Applicant.email_address.label("email_address"),
            Applicant.mobile_phone.label("mobile_phone"),
            CaseRegulationChoice.money_amount.label("money_amount"),
            CaseHandling.responsible_division_id.label("responsible_division_id"),
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
            latest_dda_sq,
            and_(
                latest_dda_sq.c.applicant_id == Applicant.id,
                latest_dda_sq.c.rn == 1,
            ),
        )
        .where(
            (
                _finance_location_visibility_condition
                if auto_expand_mother_province
                else _case_location_visibility_condition
            )(
                province_id=province_id,
                staff=staff,
                dwf_scope=dwf_scope,
                requested_province_ids=_parse_int_query_values(province_ids),
                type_money_ids=set(type_money_id) if type_money_id else None,
                province_column=Province.id,
                type_money_column=Applicant.type_money_category_id,
            )
        )
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
    applicant_ids = [row["applicant_id"] for row in rows]
    payments_by_applicant = await load_payments_by_applicant_ids(session, applicant_ids)
    enriched_rows = _merge_payment_metrics_into_rows(rows, payments_by_applicant)
    return CaseForStaffFinanceListResponse(
        province_id=province.id,
        province_name=province.name,
        total_applicants=total_applicants or 0,
        filtered_applicants=filtered_applicants or 0,
        items=[_row_to_case_for_staff_finance_read(row) for row in enriched_rows],
    )


@router.get("/finance", response_model=CaseForStaffFinanceListResponse)
async def list_cases_for_staff_finance(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการค้นหา (บังคับ)"),
    province_ids: list[str] | None = Query(
        None,
        description="DWF scope narrowing only; values must belong to the DWF group resolved from province_id/staff",
    ),
    dwf_scope: bool = Query(False, description="Use DWF/Sor Kor visibility from drpod_dwf.json"),
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
    staff: StaffClaims = Depends(require_staff),
) -> CaseForStaffFinanceListResponse:
    """รายการสำหรับตารางการเงิน — เฉพาะเคสที่ approve_case.approve_status = true."""
    return await _list_cases_for_staff_finance_impl(
        session,
        province_id,
        province_ids,
        dwf_scope,
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
        staff=staff,
        auto_expand_mother_province=True,
    )


@router.get("/finance/with-dda-ref", response_model=CaseForStaffFinanceListResponse)
async def list_cases_for_staff_finance_with_dda_ref(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการค้นหา (บังคับ)"),
    province_ids: list[str] | None = Query(
        None,
        description="DWF scope narrowing only; values must belong to the DWF group resolved from province_id/staff",
    ),
    dwf_scope: bool = Query(False, description="Use DWF/Sor Kor visibility from drpod_dwf.json"),
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
    staff: StaffClaims = Depends(require_staff),
) -> CaseForStaffFinanceListResponse:
    """เหมือน /finance แต่ดึงเฉพาะ applicant ที่มี welfare_payment ผูก welfare_dda_ref แล้ว.

    ไม่รวมเคสที่สถานะล่าสุด current_status_id >= 10 (อยู่ระหว่างการเบิกขึ้นไป).
    """
    return await _list_cases_for_staff_finance_impl(
        session,
        province_id,
        province_ids,
        dwf_scope,
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
        staff=staff,
    )


@router.patch("/welfare-payment", response_model=WelfarePaymentRead)
async def update_welfare_payment_for_staff(
    applicant_id: int = Query(..., ge=1, description="id จากตาราง applicants"),
    body: WelfarePaymentUpdate = Body(...),
    session: AsyncSession = Depends(get_session),
) -> WelfarePaymentRead:
    """บันทึก 037/038 ตามกฎรอบ DDA — คืนแถว welfare_payment ที่ถูกสร้างหรือแก้ (ใช้ id อัปโหลด PDF).

    038 ครั้งแรก: PATCH แถว is_037_or_038=null จาก bundle; ครั้งถัดไป: INSERT แถวใหม่
    037-only → สถานะ 10; 037+038 ในรอบเดียวกัน → สถานะ 3
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

    status_log: WelfareRequestStatus | None = None
    status_row: CurrentStatus | None = None
    if _welfare_payment_update_indicates_037(updates) or _welfare_payment_update_indicates_038(updates):
        status_log, status_row = await _apply_payment_status_if_needed(
            session,
            applicant_id,
            payment,
            updates,
        )

    await session.commit()
    if status_log is not None and status_log.current_status_id == CURRENT_STATUS_WITHDRAWING:
        await enqueue_status_email(
            session,
            applicant_id=applicant_id,
            status_log_id=status_log.id,
            current_status_id=status_log.current_status_id,
            current_status_color=status_row.color if status_row else None,
            remarks=status_log.remarks,
            trigger=CitizenStatusEmailTrigger.PAYMENT_037_RECORDED,
        )
    await session.refresh(payment)
    return WelfarePaymentRead.model_validate(payment)


@router.patch("/welfare-payment/batch", response_model=WelfarePaymentBatchRead)
async def update_welfare_payment_batch_for_staff(
    applicant_id: int = Query(..., ge=1, description="id จากตาราง applicants"),
    body: WelfarePaymentBatchUpdate = Body(...),
    session: AsyncSession = Depends(get_session),
) -> WelfarePaymentBatchRead:
    """บันทึก 037 และ 038 ใน transaction เดียว — สถานะ 3 เมื่อครบทั้งคู่ในรอบ."""
    batch_id = body.upload_batch_id
    user_sdshv = body.user_sdshv

    updates_038 = body.payment_038.model_dump(exclude_unset=True)
    updates_038["is_037_or_038"] = True
    updates_038["upload_batch_id"] = batch_id
    if user_sdshv is not None:
        updates_038["user_sdshv"] = user_sdshv

    payment_038 = await apply_038_update(session, applicant_id, updates_038)

    updates_037 = body.payment_037.model_dump(exclude_unset=True)
    updates_037["is_037_or_038"] = False
    updates_037["upload_batch_id"] = batch_id
    if user_sdshv is not None:
        updates_037["user_sdshv"] = user_sdshv

    payment_037 = await apply_037_update(session, applicant_id, updates_037)

    status_updates = {"upload_batch_id": batch_id, "user_sdshv": user_sdshv}
    status_log, status_row = await _apply_payment_status_if_needed(
        session,
        applicant_id,
        payment_037,
        status_updates,
    )

    await session.commit()
    if status_log is not None and status_log.current_status_id == CURRENT_STATUS_WITHDRAWING:
        await enqueue_status_email(
            session,
            applicant_id=applicant_id,
            status_log_id=status_log.id,
            current_status_id=status_log.current_status_id,
            current_status_color=status_row.color if status_row else None,
            remarks=status_log.remarks,
            trigger=CitizenStatusEmailTrigger.PAYMENT_037_RECORDED,
        )
    await session.refresh(payment_037)
    await session.refresh(payment_038)
    return WelfarePaymentBatchRead(
        payment_037=WelfarePaymentRead.model_validate(payment_037),
        payment_038=WelfarePaymentRead.model_validate(payment_038),
    )


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
    """PATCH แถวที่ระบุโดยตรง — ใช้แก้ประวัติ payment-upload-history ไม่สร้างแถว 038 ใหม่ ไม่เปลี่ยนสถานะคำร้อง."""
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
    row, is_new_upload = await save_file_payment_pdf(
        session,
        applicant_id=applicant_id,
        attachment_type_id=attachment_type_id,
        file=file,
        welfare_payment_id=welfare_payment_id,
        upload_batch_id=upload_batch_id,
        file_payment_id=file_payment_id,
    )
    if is_new_upload and attachment_type_id == ATTACHMENT_PDF_037_ID:
        await enqueue_payment_037_upload_email(
            session,
            applicant_id=applicant_id,
            file_payment_id=row.id,
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


@router.get(
    "/applicant/{applicant_id}/evidences/{evidence_id}/file",
    response_class=FileResponse,
    summary="ดาวน์โหลดไฟล์หลักฐานสำหรับเจ้าหน้าที่",
)
async def get_case_for_staff_evidence_file(
    applicant_id: int,
    evidence_id: int,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    ev = await session.get(WelfareEvidence, evidence_id)
    if ev is None or ev.applicant_id != applicant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence_not_found")

    root = resolved_upload_root().resolve()
    path = (root / ev.file_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="evidence_file_invalid_path",
        ) from e
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence_file_missing")

    suffix = path.suffix.lower()
    media = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "application/octet-stream")
    download_name = ev.file_original_name or ev.file_stored_name or path.name
    return FileResponse(path, media_type=media, filename=download_name)


@router.post(
    "/applicant/{applicant_id}/evidences",
    response_model=WelfareEvidenceUploadRead,
    status_code=status.HTTP_201_CREATED,
    summary="อัปโหลดรูปหลักฐานสำหรับเจ้าหน้าที่",
)
async def upload_case_for_staff_evidence_image(
    applicant_id: int,
    attachment_type_id: int = Form(..., ge=1),
    file_other_type_name: str | None = Form(None),
    household_member_seq: int | None = Form(None, ge=1),
    file: UploadFile = File(..., description="ไฟล์รูป (jpeg/png/webp/gif)"),
    session: AsyncSession = Depends(get_session),
) -> WelfareEvidenceUploadRead:
    normalized_other_name = await validate_welfare_evidence_upload(
        session,
        attachment_type_id,
        file_other_type_name,
    )

    household_member_id: int | None = None
    if household_member_seq is not None:
        member_row = await session.execute(
            select(HouseholdMember.id).where(
                HouseholdMember.applicant_id == applicant_id,
                HouseholdMember.seq == household_member_seq,
            )
        )
        member_id = member_row.scalar_one_or_none()
        if member_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="household_member_not_found",
            )
        household_member_id = member_id

    raw_content_type = (file.content_type or "").split(";")[0].strip().lower()
    if raw_content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="unsupported_media_type_expect_image",
        )

    blob = await file.read()
    if len(blob) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file_too_large")

    assert_image_magic_bytes(blob, allowed_exts=set(ALLOWED_IMAGE_TYPES.values()))
    ext = ALLOWED_IMAGE_TYPES[raw_content_type]

    base = resolved_upload_root()
    dest_dir = (base / str(applicant_id)).resolve()
    try:
        dest_dir.relative_to(base.resolve())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="upload_path_invalid") from e

    dest_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    full_path = dest_dir / stored
    full_path.write_bytes(blob)

    evidence = WelfareEvidence(
        attachment_type_id=attachment_type_id,
        applicant_id=applicant_id,
        file_path=f"{applicant_id}/{stored}",
        file_original_name=file.filename,
        file_stored_name=stored,
        file_size=len(blob),
        file_other_type_name=normalized_other_name,
        household_member_id=household_member_id,
    )
    session.add(evidence)
    try:
        await session.flush()
    except IntegrityError as e:
        if full_path.is_file():
            full_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    await session.refresh(evidence)
    return WelfareEvidenceUploadRead(evidence=WelfareEvidenceRead.model_validate(evidence))


@router.put(
    "/applicant/{applicant_id}/evidences/{evidence_id}",
    response_model=WelfareEvidenceUploadRead,
    summary="แก้ไขรูปหลักฐานสำหรับเจ้าหน้าที่",
)
async def update_case_for_staff_evidence_image(
    applicant_id: int,
    evidence_id: int,
    attachment_type_id: int = Form(..., ge=1),
    file_other_type_name: str | None = Form(None),
    file: UploadFile = File(..., description="ไฟล์รูปใหม่ (jpeg/png/webp/gif)"),
    session: AsyncSession = Depends(get_session),
) -> WelfareEvidenceUploadRead:
    ev = await session.get(WelfareEvidence, evidence_id)
    if ev is None or ev.applicant_id != applicant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence_not_found")

    normalized_other_name = await validate_welfare_evidence_upload(
        session,
        attachment_type_id,
        file_other_type_name,
    )

    raw_content_type = (file.content_type or "").split(";")[0].strip().lower()
    if raw_content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="unsupported_media_type_expect_image",
        )

    blob = await file.read()
    if len(blob) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file_too_large")

    assert_image_magic_bytes(blob, allowed_exts=set(ALLOWED_IMAGE_TYPES.values()))
    ext = ALLOWED_IMAGE_TYPES[raw_content_type]
    base = resolved_upload_root()
    dest_dir = (base / str(applicant_id)).resolve()
    try:
        dest_dir.relative_to(base.resolve())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="upload_path_invalid") from e

    dest_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    new_full_path = dest_dir / stored
    new_full_path.write_bytes(blob)

    old_file = (base / ev.file_path).resolve()
    old_file.unlink(missing_ok=True)

    ev.attachment_type_id = attachment_type_id
    ev.file_path = f"{applicant_id}/{stored}"
    ev.file_original_name = file.filename
    ev.file_stored_name = stored
    ev.file_size = len(blob)
    ev.file_other_type_name = normalized_other_name

    await session.flush()
    await session.refresh(ev)
    return WelfareEvidenceUploadRead(evidence=WelfareEvidenceRead.model_validate(ev))


@router.patch(
    "/applicant/{applicant_id}/evidences/{evidence_id}",
    summary="แก้ไขชื่อเอกสาร (สำหรับ attachment_type_id = อื่นๆ)",
)
async def patch_case_for_staff_evidence_name(
    applicant_id: int,
    evidence_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
) -> dict:
    ev = await session.get(WelfareEvidence, evidence_id)
    if ev is None or ev.applicant_id != applicant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence_not_found")
    if "file_other_type_name" in body:
        ev.file_other_type_name = body["file_other_type_name"]
    await session.commit()
    await session.refresh(ev)
    return {"id": ev.id, "file_other_type_name": ev.file_other_type_name}


@router.delete(
    "/applicant/{applicant_id}/evidences/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="ลบรูปหลักฐานสำหรับเจ้าหน้าที่",
)
async def delete_case_for_staff_evidence_image(
    applicant_id: int,
    evidence_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    ev = await session.get(WelfareEvidence, evidence_id)
    if ev is None or ev.applicant_id != applicant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence_not_found")

    file_path = (resolved_upload_root() / ev.file_path).resolve()
    await session.delete(ev)
    await session.flush()
    file_path.unlink(missing_ok=True)


@router.get(
    "/status-summary",
    response_model=CaseForStaffStatusSummaryResponse,
    summary="สรุปจำนวนคำร้องตาม bucket สำหรับ staff digest",
)
async def get_case_for_staff_status_summary(
    province_id: int = Query(..., description="รหัสจังหวัด"),
    session: AsyncSession = Depends(get_session),
) -> CaseForStaffStatusSummaryResponse:
    summary = await fetch_staff_digest_summary(session, province_id)
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="province_not_found")
    return summary


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
        **_process_sla_fields_from_applicant(applicant),
    )


@router.patch(
    "/responsible-division",
    response_model=CaseForStaffResponsibleDivisionRead,
    summary="อัปเดตหน่วยงานรับผิดชอบ (case_handling.responsible_division_id)",
    description=(
        "ใช้ `applicant_id` (query) หา/สร้าง `case_handling` แล้วอัปเดต `responsible_division_id` "
        "— ส่ง null เพื่อล้างค่า (ไม่บังคับเลือก)"
    ),
)
async def update_responsible_division_for_staff(
    applicant_id: int = Query(..., ge=1, description="id จากตาราง applicants"),
    body: CaseForStaffResponsibleDivisionUpdate = Body(...),
    session: AsyncSession = Depends(get_session),
) -> CaseForStaffResponsibleDivisionRead:
    applicant = await session.get(Applicant, applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    handling = await session.scalar(
        select(CaseHandling).where(CaseHandling.applicant_id == applicant_id)
    )
    if handling is None:
        handling = CaseHandling(applicant_id=applicant_id)
        session.add(handling)
        await session.flush()

    if "responsible_division_id" in body.model_fields_set:
        handling.responsible_division_id = body.responsible_division_id
    handling.updated_at = datetime.now()
    await session.commit()
    await session.refresh(handling)

    return CaseForStaffResponsibleDivisionRead(
        applicant_id=applicant_id,
        responsible_division_id=handling.responsible_division_id,
        updated_at=handling.updated_at,
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
    staff: StaffClaims = Depends(require_staff),
) -> WelfareRequestStatusRead:
    applicant = await session.get(Applicant, body.applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")
    current_status = await _get_row(session, CurrentStatus, body.current_status_id)
    if current_status is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="current_status_not_found")
    await _assert_dwf_status_change_allowed(
        session,
        staff=staff,
        applicant=applicant,
        target_status_id=body.current_status_id,
    )

    log = WelfareRequestStatus(
        applicant_id=body.applicant_id,
        current_status_id=body.current_status_id,
        remarks=body.remarks,
        update_by_sdshv=body.update_by_sdshv,
    )
    session.add(log)
    await session.flush()

    if body.current_status_id == CURRENT_STATUS_WITHDRAWING_APPROVED:
        await resolve_active_pmj_rejects_for_applicant(
            session,
            applicant_id=body.applicant_id,
        )

    maybe_freeze_process_sla_for_status(applicant, body.current_status_id)

    previous_status_id = await fetch_previous_status_id(
        session,
        applicant_id=body.applicant_id,
        before_status_log_id=log.id,
    )

    await session.commit()

    if (
        log.current_status_id == CURRENT_STATUS_PENDING_INTAKE
        and previous_status_id == CURRENT_STATUS_EDIT_REQUESTED
    ):
        await enqueue_case_submitted_email(
            session,
            applicant_id=log.applicant_id,
            idempotency_key=f"welfare-case-correction-{log.id}",
            submission_kind="correction",
        )
    else:
        await enqueue_status_email(
            session,
            applicant_id=log.applicant_id,
            status_log_id=log.id,
            current_status_id=log.current_status_id,
            current_status_color=current_status.color,
            remarks=log.remarks,
        )
    result = await session.execute(
        select(WelfareRequestStatus)
        .where(WelfareRequestStatus.id == log.id)
        .options(selectinload(WelfareRequestStatus.current_status)),
    )
    row = result.scalar_one()
    return WelfareRequestStatusRead.model_validate(row)


def _staff_sections_to_welfare_update(body: StaffCaseSectionsUpdate) -> WelfareCaseUpdate:
    applicant = None
    if body.problem_details is not None or body.family_distress is not None:
        applicant = WelfareApplicantUpdate(
            problem_details=body.problem_details,
            family_distress=body.family_distress,
        )
    return WelfareCaseUpdate(
        applicant=applicant,
        addresses=body.addresses,
        dependency_loads=body.dependency_loads,
        economic_infos=body.economic_infos,
        household_members=body.household_members,
        welfare_history=body.welfare_history,
        request_type_ids=body.request_type_ids,
        request_other_text=body.request_other_text,
        request_in_kind_text=body.request_in_kind_text,
    )


@router.patch(
    "/case-sections",
    response_model=CaseForStaffPorKor1DetailResponse,
    summary="นักสังคมฯ แก้ไขส่วนที่ 2–4 ปสค.1",
    description=(
        "อัปเดตเฉพาะ addresses, economic, dependency, household_members, "
        "welfare_history, problem_details, request_types — คืน por-kor-1-detail หลังบันทึก"
    ),
)
async def update_case_sections_for_staff(
    applicant_id: int = Query(..., ge=1, description="id จากตาราง applicants"),
    body: StaffCaseSectionsUpdate = Body(...),
    session: AsyncSession = Depends(get_session),
) -> CaseForStaffPorKor1DetailResponse:
    payload = body.model_dump(exclude_unset=True)
    if not {k for k in payload if k != "update_by_sdshv"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="at_least_one_field_required",
        )

    row = await session.get(Applicant, applicant_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    current_status_id = await fetch_latest_status_id(session, applicant_id=applicant_id)
    if current_status_id not in STAFF_CASE_SECTION_EDIT_STATUS_IDS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="case_status_not_editable",
        )

    welfare_update = _staff_sections_to_welfare_update(body)
    await apply_case_update(session, applicant_id, welfare_update)
    await record_staff_data_edit_audit(
        session,
        applicant_id=applicant_id,
        current_status_id=current_status_id,
        edit_by_sdshv=body.update_by_sdshv,
        remarks=build_staff_section_edit_remarks(payload),
        event_type=EVENT_TYPE_SECTION_EDIT,
        sections=build_staff_section_edit_sections(payload),
    )
    await session.commit()

    reloaded = await _load_full_applicant(session, applicant_id)
    if reloaded is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="reload_failed")

    if reloaded.type_money_category_id is not None and reloaded.type_money_category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="type_money_category_not_found_for_applicant",
        )

    case_read = await applicant_to_case_read(reloaded)
    return _build_por_kor_1_detail(case_read, reloaded)


@router.post(
    "/data-edit-log",
    response_model=CaseDataEditLogRead,
    status_code=status.HTTP_201_CREATED,
    summary="บันทึก timeline การแก้ไขข้อมูล",
    description=(
        "เพิ่มแถวใน case_data_edit_logs — "
        "ใช้เมื่อแก้ไขผลการเยี่ยมบ้านหรือกรณีอื่นที่ไม่ผ่าน PATCH /case-sections"
    ),
)
async def create_staff_data_edit_log(
    body: StaffDataEditLogCreate = Body(...),
    session: AsyncSession = Depends(get_session),
) -> CaseDataEditLogRead:
    applicant = await session.get(Applicant, body.applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    current_status_id = await fetch_latest_status_id(session, applicant_id=body.applicant_id)
    if current_status_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="current_status_not_found")
    if current_status_id not in STAFF_CASE_SECTION_EDIT_STATUS_IDS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="case_status_not_editable",
        )

    event_type = (body.event_type or EVENT_TYPE_SURVEY_EDIT).strip()
    if event_type not in {EVENT_TYPE_SECTION_EDIT, EVENT_TYPE_SURVEY_EDIT}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid_event_type",
        )

    if event_type == EVENT_TYPE_SURVEY_EDIT:
        remarks = (body.remarks or "").strip() or build_staff_survey_edit_remarks()
        sections = None
    else:
        remarks = (body.remarks or "").strip() or build_staff_section_edit_remarks({})
        sections = body.sections

    log = await record_staff_data_edit_audit(
        session,
        applicant_id=body.applicant_id,
        current_status_id=current_status_id,
        edit_by_sdshv=body.update_by_sdshv,
        remarks=remarks,
        event_type=event_type,
        sections=sections,
    )
    await session.commit()
    return CaseDataEditLogRead.model_validate(log)


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


@router.get(
    "/article",
    response_model=ArticleRead,
    summary="ดึง article ตาม applicant_id",
    description="คืนเนื้อหา article สำหรับแสดง — 404 เมื่อยังไม่เคยบันทึก",
)
async def get_article_for_staff(
    applicant_id: int = Query(..., ge=1, description="id จากตาราง applicants"),
    session: AsyncSession = Depends(get_session),
) -> ArticleRead:
    row = await get_article_by_applicant_id(session, applicant_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="article_not_found")
    return ArticleRead.model_validate(row)


@router.post(
    "/article",
    response_model=ArticleRead,
    status_code=status.HTTP_201_CREATED,
    summary="บันทึก article (ครั้งแรก)",
    description=(
        "สร้าง article เก็บเนื้อหาอย่างเดียว (ครั้งแรกเท่านั้น, 409 ถ้ามีแล้ว). "
        "การอนุมัติและเปลี่ยนสถานะใช้ POST /approve-case แยก"
    ),
)
async def create_article_for_staff(
    body: ArticleCreate,
    session: AsyncSession = Depends(get_session),
) -> ArticleRead:
    applicant = await session.get(Applicant, body.applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    if await get_article_by_applicant_id(session, body.applicant_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="article_already_exists")

    article_fields = body.model_dump(exclude={"applicant_id"}, exclude_none=True)
    article = await upsert_article(session, body.applicant_id, article_fields)
    await session.commit()
    await session.refresh(article)
    return ArticleRead.model_validate(article)


@router.patch(
    "/article",
    response_model=ArticleRead,
    summary="อัปเดต article (ไม่เปลี่ยนสถานะ/approve_case)",
    description="แก้ไขฟิลด์เนื้อหา article อย่างเดียว — 404 เมื่อยังไม่มี article",
)
async def patch_article_for_staff(
    applicant_id: int = Query(..., ge=1, description="id จากตาราง applicants"),
    body: ArticleUpdate = Body(...),
    session: AsyncSession = Depends(get_session),
) -> ArticleRead:
    if await get_article_by_applicant_id(session, applicant_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="article_not_found")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        row = await get_article_by_applicant_id(session, applicant_id)
        assert row is not None
        return ArticleRead.model_validate(row)

    row = await upsert_article(session, applicant_id, updates)
    await session.commit()
    await session.refresh(row)
    return ArticleRead.model_validate(row)


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

    article_id = await resolve_article_id_for_applicant(session, body.applicant_id)
    row, status_log, current_status = await record_approve_case_with_status(
        session,
        applicant_id=body.applicant_id,
        approve_status=body.approve_status,
        esignature=body.esignature,
        user_sdshv=body.user_sdshv,
        reject_reason=body.reject_reason,
        article_id=article_id,
    )
    await session.commit()
    if status_log is not None and current_status is not None:
        await enqueue_status_email(
            session,
            applicant_id=status_log.applicant_id,
            status_log_id=status_log.id,
            current_status_id=status_log.current_status_id,
            current_status_color=current_status.color,
            remarks=status_log.remarks,
        )
    await session.refresh(row)

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
    current_status = await _get_row(session, CurrentStatus, _EDIT_REQUEST_STATUS_ID)
    if current_status is None:
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
    await enqueue_status_email(
        session,
        applicant_id=status_log.applicant_id,
        status_log_id=status_log.id,
        current_status_id=status_log.current_status_id,
        current_status_color=current_status.color,
        remarks=status_log.remarks,
    )

    return WelfareEditRequestRead(
        welfare_request_status_id=status_log.id,
        comments=[
            WelfareReviewCommentRead.model_validate(c) for c in comments
        ],
    )


# ---------------------------------------------------------------------------
# TypeSend — master ประเภทการส่งข้อมูล
# ---------------------------------------------------------------------------


@router.get("/type-sends", response_model=list[TypeSendRead], summary="รายการประเภทการส่งข้อมูล (master)")
async def list_type_sends(
    session: AsyncSession = Depends(get_session),
) -> list[TypeSendRead]:
    result = await session.execute(select(TypeSend).order_by(TypeSend.id))
    return [TypeSendRead.model_validate(row) for row in result.scalars().all()]


# ---------------------------------------------------------------------------
# MoreMso — ข้อมูล MSO เพิ่มเติม 1:1 case_handling (เข้าถึงผ่าน applicant_id)
# ---------------------------------------------------------------------------


async def _get_case_handling_for_applicant(session: AsyncSession, applicant_id: int) -> CaseHandling:
    row = await session.scalar(select(CaseHandling).where(CaseHandling.applicant_id == applicant_id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_handling_not_found")
    return row


@router.get(
    "/applicant/{applicant_id}/more-mso",
    response_model=MoreMsoRead | None,
    summary="ดึงข้อมูล MSO เพิ่มเติมของ applicant (null ถ้ายังไม่มี)",
)
async def get_more_mso(
    applicant_id: int,
    session: AsyncSession = Depends(get_session),
) -> MoreMsoRead | None:
    case_handling = await _get_case_handling_for_applicant(session, applicant_id)
    row = await session.scalar(select(MoreMso).where(MoreMso.case_handling_id == case_handling.id))
    if row is None:
        return None
    return MoreMsoRead.model_validate(row)


@router.put(
    "/applicant/{applicant_id}/more-mso",
    response_model=MoreMsoRead,
    summary="สร้างหรืออัปเดตข้อมูล MSO เพิ่มเติม (upsert)",
)
async def upsert_more_mso(
    applicant_id: int,
    body: MoreMsoUpsert = Body(...),
    session: AsyncSession = Depends(get_session),
) -> MoreMsoRead:
    case_handling = await _get_case_handling_for_applicant(session, applicant_id)
    row = await session.scalar(select(MoreMso).where(MoreMso.case_handling_id == case_handling.id))
    payload = body.model_dump()
    if row is None:
        row = MoreMso(case_handling_id=case_handling.id, **payload)
        session.add(row)
    else:
        for field, value in payload.items():
            setattr(row, field, value)
    await session.commit()
    await session.refresh(row)
    return MoreMsoRead.model_validate(row)


# ---------------------------------------------------------------------------
# SendData — บันทึกการส่งข้อมูลคำร้อง N:1 applicants
# ---------------------------------------------------------------------------


@router.get(
    "/applicant/{applicant_id}/send-data",
    response_model=list[SendDataRead],
    summary="ประวัติการส่งข้อมูลของ applicant",
)
async def list_send_data(
    applicant_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[SendDataRead]:
    applicant = await session.get(Applicant, applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")
    result = await session.execute(
        select(SendData).where(SendData.applicant_id == applicant_id).order_by(SendData.id.asc())
    )
    return [SendDataRead.model_validate(row) for row in result.scalars().all()]


@router.post(
    "/applicant/{applicant_id}/send-data",
    response_model=SendDataRead,
    status_code=status.HTTP_201_CREATED,
    summary="บันทึกการส่งข้อมูลคำร้อง",
)
async def create_send_data(
    applicant_id: int,
    body: SendDataCreate = Body(...),
    session: AsyncSession = Depends(get_session),
) -> SendDataRead:
    applicant = await session.get(Applicant, applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")
    type_send = await session.get(TypeSend, body.type_send_id)
    if type_send is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="type_send_not_found")
    row = SendData(applicant_id=applicant_id, **body.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return SendDataRead.model_validate(row)


# ---------------------------------------------------------------------------
# MSO forward — ส่งต่อกระทรวง / MSO logbook (คีย์ send_channel)
# ---------------------------------------------------------------------------


def _mso_forward_read_from_row(row: SendData) -> MsoForwardRead:
    channel = TYPE_SEND_ID_TO_CHANNEL[row.type_send_id]
    return MsoForwardRead(
        id=row.id,
        applicant_id=row.applicant_id,
        send_channel=channel,
        type_send_id=row.type_send_id,
        send_by_sdshv=row.send_by_sdshv,
        json_case=row.json_case,
        response_code=row.response_code,
        response_text=row.response_text,
    )


@router.get(
    "/applicant/{applicant_id}/mso-forward-status",
    response_model=MsoForwardStatusRead,
    summary="ตรวจว่าส่งต่อกระทรวง / MSO logbook แล้วหรือยัง",
)
async def get_mso_forward_status(
    applicant_id: int,
    session: AsyncSession = Depends(get_session),
) -> MsoForwardStatusRead:
    data = await fetch_mso_forward_status(session, applicant_id)
    return MsoForwardStatusRead.model_validate(data)


@router.post(
    "/applicant/{applicant_id}/mso-forward",
    response_model=MsoForwardRead,
    status_code=status.HTTP_201_CREATED,
    summary="บันทึกการส่งต่อ (กระทรวง หรือ MSO logbook)",
)
async def create_mso_forward(
    applicant_id: int,
    body: MsoForwardCreate = Body(...),
    session: AsyncSession = Depends(get_session),
) -> MsoForwardRead:
    row = await record_mso_forward(
        session,
        applicant_id=applicant_id,
        send_channel=body.send_channel,
        send_by_sdshv=body.send_by_sdshv,
        json_case=body.json_case,
        response_code=body.response_code,
        response_text=body.response_text,
    )

    status_log: WelfareRequestStatus | None = None
    if body.send_channel == "ministry":
        latest_status_id = await fetch_latest_status_id(session, applicant_id=applicant_id)
        if latest_status_id != CURRENT_STATUS_MSO_FORWARDED:
            applicant = await session.get(Applicant, applicant_id)
            if applicant is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="applicant_not_found",
                )
            current_status = await session.get(CurrentStatus, CURRENT_STATUS_MSO_FORWARDED)
            if current_status is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="current_status_not_found",
                )

            status_log = WelfareRequestStatus(
                applicant_id=applicant_id,
                current_status_id=CURRENT_STATUS_MSO_FORWARDED,
                remarks="ส่งต่อข้อมูลเข้ากระทรวงเรียบร้อยแล้ว",
                update_by_sdshv=body.send_by_sdshv,
            )
            session.add(status_log)
            await session.flush()

            # status id 11 ไม่ได้อยู่ในกลุ่ม freeze ของ SLA
            maybe_freeze_process_sla_for_status(applicant, CURRENT_STATUS_MSO_FORWARDED)

    await session.commit()

    if status_log is not None:
        await enqueue_status_email(
            session,
            applicant_id=status_log.applicant_id,
            status_log_id=status_log.id,
            current_status_id=status_log.current_status_id,
            current_status_color=None,
            remarks=status_log.remarks,
        )

    return _mso_forward_read_from_row(row)


@router.post(
    "/cover-document-batch",
    response_model=CoverDocumentBatchRead,
    status_code=status.HTTP_201_CREATED,
    summary="สร้าง cover document batch + ผูก applicant_ids",
)
async def create_cover_document_batch_for_staff(
    body: CoverDocumentBatchCreate,
    session: AsyncSession = Depends(get_session),
) -> CoverDocumentBatchRead:
    batch = await create_cover_document_batch(session, body.model_dump(exclude_none=True))
    await session.commit()
    batch = await get_cover_document_batch(session, batch.id)
    return CoverDocumentBatchRead.model_validate(batch_to_read(batch))


@router.patch(
    "/cover-document-batch/{batch_id}",
    response_model=CoverDocumentBatchRead,
    summary="แก้ header cover document batch ที่เดียว",
)
async def patch_cover_document_batch_for_staff(
    batch_id: int,
    body: CoverDocumentBatchUpdate,
    session: AsyncSession = Depends(get_session),
    staff: StaffClaims = Depends(require_staff),
) -> CoverDocumentBatchRead:
    existing = await get_cover_document_batch(session, batch_id)
    _assert_cover_document_batch_visible_to_staff(existing, staff)
    batch = await update_cover_document_batch(
        session,
        batch_id,
        body.model_dump(exclude_none=True),
    )
    await session.commit()
    batch = await get_cover_document_batch(session, batch.id)
    return CoverDocumentBatchRead.model_validate(batch_to_read(batch))


@router.get(
    "/cover-document-batch/{batch_id}",
    response_model=CoverDocumentBatchRead,
    summary="ดึง cover document batch พร้อมสมาชิก",
)
async def get_cover_document_batch_for_staff(
    batch_id: int,
    session: AsyncSession = Depends(get_session),
    staff: StaffClaims = Depends(require_staff),
) -> CoverDocumentBatchRead:
    batch = await get_cover_document_batch(session, batch_id)
    _assert_cover_document_batch_visible_to_staff(batch, staff)
    return CoverDocumentBatchRead.model_validate(batch_to_read(batch))


@router.get(
    "/cover-document-batch",
    response_model=CoverDocumentBatchListResponse,
    summary="รายการ cover document batch",
)
async def list_cover_document_batches_for_staff(
    province_id: int | None = Query(None, ge=1),
    pending: bool = Query(False),
    session: AsyncSession = Depends(get_session),
    staff: StaffClaims = Depends(require_staff),
) -> CoverDocumentBatchListResponse:
    sor_kor_province_ids: tuple[int, ...] | None = None
    if province_id is not None and not staff.is_internal:
        sor_kor_province_ids = allowed_sor_kor_province_ids(staff.province_id)
    batches = await list_cover_document_batches(
        session,
        province_id=province_id,
        pending=pending,
        sor_kor_province_ids=sor_kor_province_ids,
        sor_kor_type_money_id=SOR_KOR_TYPE_MONEY_ID,
    )
    return CoverDocumentBatchListResponse(
        items=[CoverDocumentBatchRead.model_validate(batch_to_read(batch)) for batch in batches]
    )
