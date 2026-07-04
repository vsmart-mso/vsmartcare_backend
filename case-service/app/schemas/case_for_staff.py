"""สคีมารายการคำร้องสำหรับหน้าจอเจ้าหน้าที่."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .case_data_edit_log import CaseDataEditLogRead
from .process_sla import ProcessSlaFields
from .address import AddressRead
from .applicant import ApplicantRead
from .dependency import DependencyLoadRead
from .economic import EconomicInfoRead, HouseholdMemberRead
from .person import PersonRead
from .status_log import WelfareRequestStatusRead
from .welfare import (
    WelfareEvidenceRead,
    WelfareHistoryDetailRead,
    WelfareHistoryRead,
    WelfareRequestTypeRead,
)
from .review import ReviewFieldRead
from .case_welfare import (
    AddressInCase,
    DependencyLoadInCase,
    EconomicInfoInCase,
    HouseholdMemberInCase,
    WelfareHistoryInCase,
)


class KtbSubmissionAuditFields(BaseModel):
    """ฟิลด์ snapshot Require KTB — default เคสเก่าก่อน migration."""

    require_ktb_corporate: bool = Field(
        True,
        description="true = ต้องมีเอกสาร KTB Corporate Online ใหม่",
    )
    require_ktb_reason: str = Field(
        "NEW_CASE",
        max_length=32,
        description="NEW_CASE | NONE | ACCOUNT_CHANGED | PROVINCE_CHANGED",
    )
    existing_case_source: str | None = Field(None, max_length=16)
    existing_case_detected_sources: list[str] | None = Field(
        None,
        description="แหล่งที่พบรายเดิมตอน snapshot เช่น vcare_main, vsmart_main",
    )
    existing_case_ref_id: int | None = None
    existing_case_province_id: int | None = None
    existing_case_province_name: str | None = Field(None, max_length=255)
    submission_province_id: int | None = None
    submission_province_name: str | None = Field(None, max_length=255)
    is_account_changed: bool | None = None
    has_ktb_evidence: bool = Field(
        False,
        description="มี welfare_evidences attachment type 11",
    )
    prior_ktb_reuse_applicant_id: int | None = Field(
        None,
        description="เมื่อ require=false และ prior มาจาก VCARE — อ้างอิงเคสเดิม",
    )


class CaseForStaffRead(ProcessSlaFields, KtbSubmissionAuditFields):
    applicant_id: int
    case_number: str | None = Field(None, max_length=100)
    current_status_id: int | None = None
    current_status: str | None = None
    current_status_color: str | None = Field(None, max_length=32)
    type_money_id: int | None = None
    type_money_id_name: str | None = Field(None, max_length=255)
    type_money_id_color: str | None = Field(None, max_length=32)
    type_money_name_acronym: str | None = Field(None, max_length=255)
    sw_explorer_sdshv: str | None = Field(None, max_length=255)
    firstname: str = Field(..., min_length=1, max_length=255)
    lastname: str = Field(..., min_length=1, max_length=255)
    cid: str = Field(..., min_length=13, max_length=13)
    person_age: int = Field(..., ge=0, description="อายุ (ปี) คำนวณจาก persons.birth_date ณ วันที่เรียก API")
    datetime_create: datetime
    is_emergency: bool
    is_existing_case: bool
    time_count_process: int | None = Field(None, ge=0)
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    district_id: int
    district_name: str = Field(..., min_length=1, max_length=255)
    subdistrict_id: int
    subdistrict_name: str = Field(..., min_length=1, max_length=255)
    subdistrict_postcode_id: int
    postcode: str = Field(..., min_length=1, max_length=10)
    count_037: int = Field(0, ge=0, description="จำนวนแถว welfare_payment ที่ is_037_or_038 = false (037)")
    count_038: int = Field(
        0,
        ge=0,
        description="จำนวนครั้งที่บันทึก 038 (นับแถว welfare_payment ที่ is_037_or_038 = true)",
    )
    is_037_or_038: bool | None = Field(
        None,
        description=(
            "is_037_or_038 จาก welfare_payment ล่าสุด (เรียง id desc); "
            "null = ยังไม่มี payment หรือยังไม่ระบุ; false = 037; true = 038"
        ),
    )
    have_dda_ref: bool = Field(
        False,
        description="true เมื่อ applicant มี welfare_payment ผูก welfare_dda_ref แล้ว",
    )
    is_approved: bool = Field(
        False,
        description="true เมื่อ applicant มีแถว approve_case ที่ approve_status = true",
    )
    previous_status_id: int | None = Field(
        None,
        description="current_status_id ของ log ก่อนหน้า (rn=2) — null เมื่อมีสถานะเดียว",
    )
    is_return_edit_resubmitted: bool = Field(
        False,
        description="true เมื่อเคสเคยถูกส่งกลับเป็น status 8 และเคยมี status 1 หลังจากนั้น",
    )
    is_pmj_rejected: bool = Field(
        False,
        description="true เมื่อ applicant มี active PMJ reject (approve_status=false และ reject_resolved_at ยังว่าง)",
    )
    pmj_reject_reason: str | None = Field(
        None,
        description="เหตุผลล่าสุดที่ พมจ. ไม่อนุมัติ จาก active PMJ reject",
    )
    prior_self_submit_case_numbers: list[str] = Field(
        default_factory=list,
        description="หมายเลขคำร้อง self-submit อื่นในปีงบเดียวกัน — เฉพาะแถวล่าสุดของบุคคลนั้น",
    )
    self_submit_fiscal_year_count: int = Field(
        0,
        ge=0,
        description="จำนวนคำร้อง self-submit ของบุคคลเดียวกันในปีงบเดียวกัน — ≥2 เมื่อยื่นซ้ำ (ทุกแถวในกลุ่ม)",
    )
    self_submit_fiscal_year_case_numbers: list[str] = Field(
        default_factory=list,
        description="หมายเลขคำร้อง self-submit ทั้งหมดในปีงบเดียวกัน — ทุกแถวในกลุ่มได้รายการเดียวกัน เรียง created_at ASC",
    )
    responsible_division_id: int | None = Field(
        None,
        ge=1,
        description="Division.id จาก vSmart (case_handling.responsible_division_id)",
    )


class CaseForStaffListResponse(BaseModel):
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    total_applicants: int = Field(..., ge=0, description="จำนวน Applicant ทั้งหมดในจังหวัด")
    filtered_applicants: int = Field(..., ge=0, description="จำนวน Applicant หลังใช้ filter")
    items: list[CaseForStaffRead] = Field(default_factory=list)


class CaseForStaffStatusSummaryResponse(BaseModel):
    """สรุปจำนวนคำร้องตาม bucket สำหรับ staff digest (จังหวัดเดียว)."""

    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    total_applicants: int = Field(..., ge=0, description="จำนวน Applicant ทั้งหมดในจังหวัด")
    social_worker_pending: int = Field(
        0,
        ge=0,
        description="สถานะล่าสุด รอรับเรื่อง (current_status_id = 1)",
    )
    withdrawing_in_progress: int = Field(
        0,
        ge=0,
        description="สถานะล่าสุด อยู่ระหว่างการเบิก (current_status_id 3 หรือ 10)",
    )
    pmj_pending_approve: int = Field(
        0,
        ge=0,
        description="อยู่ระหว่างการเบิก และยังไม่มี approve_case.approve_status = true (รออนุมัติ)",
    )
    finance_pending: int = Field(
        0,
        ge=0,
        description="อยู่ระหว่างการเบิก และมี approve_case.approve_status = true (รอการเบิกจ่าย)",
    )
    social_worker_emergency: int = Field(
        0,
        ge=0,
        description="รอรับเรื่อง และ applicants.is_emergency = true",
    )
    pmj_emergency: int = Field(
        0,
        ge=0,
        description="รออนุมัติ (อยู่ระหว่างเบิก ยังไม่อนุมัติ) และ is_emergency = true",
    )
    finance_emergency: int = Field(
        0,
        ge=0,
        description="รอการเบิกจ่าย (อยู่ระหว่างเบิก อนุมัติแล้ว) และ is_emergency = true",
    )


class CaseForStaffFinanceRead(CaseForStaffRead):
    """แถวตารางการเงิน — ข้อมูลพื้นฐาน + สรุป welfare_payment (count_037/038) + DDA และธนาคาร."""

    bank_name_id: int | None = Field(None, ge=1, description="applicants.bank_name_id")
    bank_code: str | None = Field(None, max_length=10, description="bank_name.bank_code")
    bank_account_no: str | None = Field(None, max_length=50, description="applicants.bank_account_no")
    email_address: str | None = Field(None, max_length=255, description="applicants.email_address")
    mobile_phone: str | None = Field(None, max_length=20, description="applicants.mobile_phone")
    money_amount: Decimal | None = Field(
        None,
        ge=0,
        description="case_regulation_choice.money_amount (ผ่าน case_handling)",
    )
    dda_ref: str | None = Field(None, max_length=255, description="dda_ref ล่าสุดจาก welfare_dda_ref (ผ่าน welfare_payment)")


class CaseForStaffFinanceListResponse(BaseModel):
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    total_applicants: int = Field(
        ...,
        ge=0,
        description="จำนวน Applicant ในจังหวัดที่มี approve_case.approve_status = true",
    )
    filtered_applicants: int = Field(..., ge=0, description="จำนวน Applicant หลังใช้ filter")
    items: list[CaseForStaffFinanceRead] = Field(default_factory=list)


class CaseForStaffWelfareRequestStatusCreate(BaseModel):
    """บันทึกสถานะใหม่ใน welfare_request_status (อ้างอิง applicant + current_status)."""

    applicant_id: int = Field(..., ge=1)
    current_status_id: int = Field(..., ge=1)
    remarks: str | None = None
    update_by_sdshv: str | None = Field(None, max_length=255)


class StaffCaseSectionsUpdate(BaseModel):
    """นักสังคมฯ แก้ได้เฉพาะส่วนที่ 2–4 ปสค.1."""

    addresses: list[AddressInCase] | None = None
    dependency_loads: list[DependencyLoadInCase] | None = None
    economic_infos: list[EconomicInfoInCase] | None = None
    household_members: list[HouseholdMemberInCase] | None = None
    welfare_history: WelfareHistoryInCase | None = None
    problem_details: str | None = None
    family_distress: str | None = None
    request_type_ids: list[int] | None = None
    request_other_text: str | None = Field(None, max_length=500)
    request_in_kind_text: str | None = Field(None, max_length=500)
    update_by_sdshv: str | None = Field(None, max_length=255)


class CaseForStaffResponsibleDivisionUpdate(BaseModel):
    """อัปเดตหน่วยงานรับผิดชอบบน case_handling — ส่ง null เพื่อล้างค่า."""

    responsible_division_id: int | None = Field(
        None,
        ge=1,
        description="Division.id จาก vSmart — ส่ง null เพื่อล้างค่า",
    )


class CaseForStaffResponsibleDivisionRead(BaseModel):
    applicant_id: int
    responsible_division_id: int | None = None
    updated_at: datetime


class CaseForStaffApplicantStaffFieldsUpdate(BaseModel):
    """อัปเดตฟิลด์ฝั่งเจ้าหน้าที่บนตาราง applicants — ส่งเฉพาะฟิลด์ที่ต้องการเปลี่ยน."""

    type_money_category_id: int | None = Field(
        None,
        ge=1,
        description="ประเภทเงินช่วยเหลือ — ส่ง null เพื่อล้างค่า",
    )
    sw_explorer_sdshv: str | None = Field(
        None,
        max_length=255,
        description="รหัส/ชื่อผู้สำรวจ SDSHV — ส่ง null เพื่อล้างค่า",
    )


class CaseForStaffApplicantStaffFieldsRead(ProcessSlaFields):
    """ผลลัพธ์หลังอัปเดต type_money_category_id / sw_explorer_sdshv."""

    applicant_id: int
    type_money_category_id: int | None = None
    type_money_name: str | None = Field(None, max_length=255)
    type_money_name_acronym: str | None = Field(None, max_length=255)
    type_money_color: str | None = Field(None, max_length=32)
    sw_explorer_sdshv: str | None = Field(None, max_length=255)
    is_emergency: bool = False
    time_count_process: int | None = Field(None, ge=0)
    updated_at: datetime


class PorKor1TypeMoney(BaseModel):
    """ประเภทเงินช่วยเหลือจาก applicants.type_money_category_id + master — ไม่ใช้เมื่อ FK ว่าง."""

    type_money_category_id: int = Field(..., ge=1)
    name: str | None = Field(None, max_length=255)
    name_acronym: str | None = Field(None, max_length=255)
    color: str | None = Field(None, max_length=32)


class PorKor1Summary(ProcessSlaFields, KtbSubmissionAuditFields):
    """สรุปอ้างอิงคำร้อง — ใช้หัวจอสรุป / ระบบอื่น."""

    applicant_id: int
    case_number: str | None = Field(None, max_length=100)
    type_money: PorKor1TypeMoney | None = Field(
        None,
        description="null เมื่อ applicants.type_money_category_id ว่าง — มิฉะนั้นมี id และข้อมูลจาก master",
    )
    is_emergency: bool
    is_existing_case: bool
    time_count_process: int | None = Field(None, ge=0)
    sw_explorer_sdshv: str | None = Field(None, max_length=255)
    applicant_created_at: datetime
    applicant_updated_at: datetime
    can_edit_case_sections: bool = Field(
        False,
        description=(
            "true เมื่อ current_status_id ∈ {1, 2, 3, 8} — "
            "อนุญาตให้นักสังคมฯ แก้ไขส่วนที่ 2–4 และผลการเยี่ยมบ้าน"
        ),
    )
    responsible_division_id: int | None = Field(
        None,
        description="หน่วยงานรับผิดชอบ (Division.id จาก vSmart)",
    )


class StaffDataEditLogCreate(BaseModel):
    """บันทึก timeline การแก้ไขข้อมูล — ไม่เปลี่ยนสถานะคำร้อง."""

    applicant_id: int = Field(..., ge=1)
    event_type: str = Field(
        "survey_edit",
        max_length=32,
        description="section_edit | survey_edit",
    )
    sections: list[int] | None = Field(
        None,
        description="section ปสค.1 ที่แก้ — ใช้กับ event_type=section_edit",
    )
    remarks: str | None = Field(
        None,
        max_length=2000,
        description="หมายเหตุ — default ใช้ข้อความมาตรฐานเมื่อว่าง",
    )
    update_by_sdshv: str | None = Field(
        None,
        max_length=255,
        description="PK Data_sdhsv ของผู้แก้ไข",
    )


class PorKor1PersonSection(BaseModel):
    """ข้อมูลบุคคล (ตาราง persons) — ชื่อ บัตร วันเกิด ฯลฯ."""

    person: PersonRead
    prefix_name: str | None = Field(None, max_length=255, description="ชื่อคำนำหน้าจาก master")


class PorKor1ApplicantSection(BaseModel):
    """ข้อมูลผู้ขอรับสวัสดิการและการติดต่อ (ตาราง applicants + master ที่เกี่ยวข้อง)."""

    record: ApplicantRead
    requester_relation_type_name: str | None = Field(None, max_length=255)
    marital_status_name: str | None = Field(None, max_length=255)
    bank_name: str | None = Field(None, max_length=255)


class PorKor1AddressItem(BaseModel):
    """หนึ่งที่อยู่ของผู้ยื่น พร้อมชื่อประเภทที่อยู่ (ทะเบียนบ้าน / ปัจจุบัน ฯลฯ)."""

    address: AddressRead
    address_type_name: str | None = Field(None, max_length=255)
    province_id: int | None = Field(None, description="รหัสจังหวัดจาก master (ผ่าน sub_districts_postcode)")
    province_name: str | None = Field(None, max_length=255)
    district_id: int | None = Field(None, description="รหัสอำเภอจาก master")
    district_name: str | None = Field(None, max_length=255)
    subdistrict_id: int | None = Field(None, description="รหัสตำบลจาก master")
    subdistrict_name: str | None = Field(None, max_length=255)
    postcode: str | None = Field(None, max_length=10, description="รหัสไปรษณีย์ (ค่าจากตาราง postcode.name)")


class PorKor1DependencyItem(BaseModel):
    """ภาระการเลี้ยงดูหนึ่งรายการ พร้อมชื่อประเภทจาก master."""

    dependency: DependencyLoadRead
    dependency_type_name: str | None = Field(None, max_length=255)


class PorKor1EconomicItem(BaseModel):
    """ข้อมูลเศรษฐกิจหนึ่งชุด พร้อมชื่อประเภทที่อยู่อาศัย (ถ้ามี)."""

    economic: EconomicInfoRead
    housing_type_name: str | None = Field(None, max_length=255)
    occupation_type_name: str | None = Field(
        None, max_length=255, description="ชื่ออาชีพผู้ยื่นจาก master (occupation_types)"
    )
    family_occupation_type_name: str | None = Field(
        None, max_length=255, description="ชื่ออาชีพหลักของครอบครัวจาก master (occupation_types)"
    )


class PorKor1WelfareRequestTypeItem(BaseModel):
    """ประเภทคำร้องที่ขอหนึ่งรายการ พร้อมชื่อจาก master."""

    item: WelfareRequestTypeRead
    request_type_name: str | None = Field(None, max_length=255)
    request_other_text: str | None = Field(
        None,
        max_length=500,
        description=(
            "ข้อความระบุรายละเอียดเมื่อขอประเภท 'ช่วยเหลือเรื่องอื่นๆ' — "
            "คอลัมน์ `welfare_request_types.request_other_text` (สะดวกแสดงผลโดยไม่ต้องอ่านจาก `item`)"
        ),
    )
    money_amount: Decimal | None = Field(
        None,
        ge=0,
        description=(
            "จำนวนเงินที่ช่วยเหลือ (หน้า 11) — `case_regulation_choice.money_amount` "
            "ผ่าน `case_handling` ของ applicant (เดียวกันทุกแถวในคำร้องนี้หากมีข้อมูล)"
        ),
    )


class PorKor1WelfareHistoryDetailRead(WelfareHistoryDetailRead):
    """รายการประวัติสวัสดิการ — ฟิลด์เดิมของ WelfareHistoryDetailRead + ชื่อ master."""

    received_welfare_type_name: str | None = Field(
        None,
        max_length=255,
        description="ชื่อจากตาราง received_welfare_types",
    )


class PorKor1WelfareHistoryRead(WelfareHistoryRead):
    """ประวัติการรับสวัสดิการในอดีต — history_details มี received_welfare_type_name."""

    history_details: list[PorKor1WelfareHistoryDetailRead] = Field(default_factory=list)


class PorKor1WelfareRequestStatusSection(BaseModel):
    """สถานะคำร้อง — ล่าสุดและประวัติทั้งหมด (เรียงจากใหม่ไปเก่า)."""

    latest: WelfareRequestStatusRead | None = None
    history: list[WelfareRequestStatusRead] = Field(default_factory=list)


class ReturnEditCommentItem(BaseModel):
    """หนึ่งรายการ field ที่เคยถูกส่งกลับแก้ไข พร้อมเหตุผลและ step."""

    review_field_id: int
    label: str = Field(..., description="ชื่อ field จาก review_field.label")
    step: int = Field(..., description="ขั้นตอนที่ field อยู่ (1-4)")
    reason: str = Field(..., description="เหตุผลที่เจ้าหน้าที่กรอกตอนตีกลับ")


class PorKor1ReturnEditSection(BaseModel):
    """ข้อมูลการส่งกลับแก้ไขล่าสุด — comments ต่อ field + remarks รวม."""

    comments: list[ReturnEditCommentItem] = Field(default_factory=list)
    remarks: str | None = Field(None, description="หมายเหตุรวมจากเจ้าหน้าที่ (welfare_request_status.remarks)")


class PorKor1EvidenceItem(BaseModel):
    """หลักฐานแนบหนึ่งไฟล์ พร้อมชื่อประเภทเอกสารและ path สำหรับ GET รูป."""

    evidence: WelfareEvidenceRead
    attachment_type_name: str | None = Field(None, max_length=255)
    view_path: str = Field(
        ...,
        description="path สำหรับ GET ไฟล์รูป — ต่อกับ base URL ของ case-service หรือ BFF",
    )


class PorKor1MemberEvidenceItem(BaseModel):
    """หลักฐานเอกสารของสมาชิกในครัวเรือน 1 ไฟล์."""

    evidence_id: int
    attachment_type_id: int
    attachment_type_name: str | None = None
    file_other_type_name: str | None = None
    view_path: str = Field(..., description="path GET ไฟล์รูป")


class PorKor1HouseholdMemberItem(HouseholdMemberRead):
    """สมาชิกในครัวเรือนพร้อมรูปเอกสารของสมาชิก."""

    member_evidences: list[PorKor1MemberEvidenceItem] = Field(default_factory=list)


class CaseForStaffPorKor1DetailResponse(BaseModel):
    """รายละเอียดคำร้อง ปศค 1 จัดกลุ่มสำหรับนำไปแสดงในระบบอื่น (บุคคล ที่อยู่ ฯลฯ)."""

    summary: PorKor1Summary = Field(..., description="สรุปคำร้อง — type_money เป็น null เมื่อไม่มี FK ประเภทเงิน")
    person: PorKor1PersonSection = Field(..., description="ข้อมูลบุคคล")
    applicant: PorKor1ApplicantSection = Field(..., description="ข้อมูลผู้ขอรับสวัสดิการ / การติดต่อ")
    addresses: list[PorKor1AddressItem] = Field(
        default_factory=list,
        description="ข้อมูลที่อยู่ทั้งหมดของผู้ยื่น",
    )
    dependency_loads: list[PorKor1DependencyItem] = Field(
        default_factory=list,
        description="ภาระการเลี้ยงดู / ผู้ที่ต้องดูแล",
    )
    economic_infos: list[PorKor1EconomicItem] = Field(
        default_factory=list,
        description="ข้อมูลทางเศรษฐกิจและรายได้",
    )
    household_members: list[PorKor1HouseholdMemberItem] = Field(
        default_factory=list,
        description="รายละเอียดสมาชิกในครัวเรือน พร้อม member_evidences ของแต่ละคน",
    )
    welfare_request_types: list[PorKor1WelfareRequestTypeItem] = Field(
        default_factory=list,
        description="ประเภทคำร้องที่ขอ",
    )
    welfare_history: PorKor1WelfareHistoryRead | None = Field(
        None,
        description="ประวัติการรับสวัสดิการในอดีต — แต่ละ history_details มี received_welfare_type_name",
    )
    welfare_request_status: PorKor1WelfareRequestStatusSection = Field(
        ...,
        description="สถานะคำร้อง (ล่าสุด + ประวัติ)",
    )
    evidences: list[PorKor1EvidenceItem] = Field(
        default_factory=list,
        description="หลักฐานแนบ (รูป) พร้อม path สำหรับนำไปแสดง",
    )
    return_edit: PorKor1ReturnEditSection | None = Field(
        None,
        description=(
            "ข้อมูลการส่งกลับแก้ไขล่าสุด (status 8) — null เมื่อไม่เคยถูกตีกลับหรือ review_comments ว่าง"
        ),
    )
    data_edit_logs: list[CaseDataEditLogRead] = Field(
        default_factory=list,
        description="timeline การแก้ไขข้อมูลโดยนักสังคมฯ (ใหม่สุดก่อน)",
    )


# ---------------------------------------------------------------------------
# TypeSend — master ประเภทการส่งข้อมูล
# ---------------------------------------------------------------------------


class TypeSendRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    detail: str | None = None


# ---------------------------------------------------------------------------
# MoreMso — ข้อมูล MSO เพิ่มเติม 1:1 case_handling
# ---------------------------------------------------------------------------


class MoreMsoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_handling_id: int
    follow_date: str | None = None
    help_number: str | None = None
    help_date: date | None = None
    approve_name: str | None = None
    approve_number: str | None = None
    approve_date: date | None = None
    receive_date: date | None = None
    cashier: str | None = None
    cashier_name: str | None = None
    follower_name: str | None = None
    follower_position_vsmart_id: str | None = None
    follower_department_vsmart_id: str | None = None
    follower_tel: str | None = None
    follower_date: date | None = None
    follower_result: str | None = None
    follower_method: int | None = None
    follower_type: int | None = None


class MoreMsoUpsert(BaseModel):
    follow_date: str | None = Field(None, max_length=255)
    help_number: str | None = Field(None, max_length=255)
    help_date: date | None = None
    approve_name: str | None = Field(None, max_length=255)
    approve_number: str | None = Field(None, max_length=255)
    approve_date: date | None = None
    receive_date: date | None = None
    cashier: str | None = Field(None, max_length=255)
    cashier_name: str | None = Field(None, max_length=255)
    follower_name: str | None = Field(None, max_length=255)
    follower_position_vsmart_id: str | None = Field(None, max_length=255)
    follower_department_vsmart_id: str | None = Field(None, max_length=255)
    follower_tel: str | None = Field(None, max_length=255)
    follower_date: date | None = None
    follower_result: str | None = None
    follower_method: int | None = None
    follower_type: int | None = None


# ---------------------------------------------------------------------------
# SendData — บันทึกการส่งข้อมูลคำร้อง
# ---------------------------------------------------------------------------


class SendDataRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    applicant_id: int
    type_send_id: int
    type_send: TypeSendRead | None = None
    send_by_sdshv: str | None = None
    json_case: dict[str, Any] | None = None
    response_code: str | None = None
    response_text: str | None = None


class SendDataCreate(BaseModel):
    type_send_id: int = Field(..., ge=1)
    send_by_sdshv: str | None = Field(None, max_length=255)
    json_case: dict[str, Any] | None = None
    response_code: str | None = Field(None, max_length=255)
    response_text: str | None = None


# ---------------------------------------------------------------------------
# MSO forward — ส่งต่อกระทรวง / MSO logbook (อ้างอิง send_data + type_send)
# ---------------------------------------------------------------------------

MsoForwardChannelLiteral = Literal["ministry", "logbook"]


class MsoForwardCreate(BaseModel):
    """บันทึกการส่งต่อ — ใช้ send_channel แทน type_send_id."""

    send_channel: MsoForwardChannelLiteral = Field(
        ...,
        description="`ministry` = ส่งต่อเข้าหระทรวง (type_send_id=1), `logbook` = ส่งต่อ MSO logbook (type_send_id=2)",
    )
    send_by_sdshv: str | None = Field(None, max_length=255)
    json_case: dict[str, Any] | None = Field(
        None,
        description="payload ที่ส่งออก (เก็บ audit)",
    )
    response_code: str | None = Field(None, max_length=255)
    response_text: str | None = None


class MsoForwardChannelStatus(BaseModel):
    send_channel: MsoForwardChannelLiteral
    type_send_id: int
    sent: bool = Field(..., description="true ถ้ามีแถว send_data ของช่องทางนี้แล้ว (อย่างน้อย 1 ครั้ง)")
    latest_send_data_id: int | None = None


class MsoForwardStatusRead(BaseModel):
    applicant_id: int
    ministry: MsoForwardChannelStatus
    logbook: MsoForwardChannelStatus


class MsoForwardRead(BaseModel):
    """ผลลัพธ์หลังบันทึกการส่งต่อ."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    applicant_id: int
    send_channel: MsoForwardChannelLiteral
    type_send_id: int
    send_by_sdshv: str | None = None
    json_case: dict[str, Any] | None = None
    response_code: str | None = None
    response_text: str | None = None
