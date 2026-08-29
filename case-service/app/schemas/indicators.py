"""สคีมาตัวชี้วัดเงินช่วยเหลือ พม Care (Indicators API)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class IndicatorCaseStatus(str, Enum):
    """เลือกชุดสถานะล่าสุดที่นับใน indicators."""

    aided = "aided"  # ช่วยเหลือแล้ว (4)
    forwarded = "forwarded"  # ส่งต่อกระทรวงแล้ว (11)


class IndicatorFilterMeta(BaseModel):
    case_status: IndicatorCaseStatus = Field(
        ...,
        description="โหมดสถานะที่เลือก — aided=ช่วยเหลือแล้ว / forwarded=ส่งต่อแล้ว",
    )
    latest_status_id: int = Field(
        ...,
        description="สถานะหลักของโหมดที่เลือก — aided→4, forwarded→11",
    )
    aided_status_id: int = Field(..., description="สถานะที่ใช้หา aided_at — ช่วยเหลือแล้ว (4)")


class IndicatorNationwideFilterMeta(IndicatorFilterMeta):
    """filter meta ของ nationwide — รวม optional filters ที่ส่งมา."""

    province_ids: list[int] | None = Field(
        None,
        description="กรอง effective_province — null = ไม่กรองจังหวัด",
    )
    type_money_category_ids: list[int] | None = Field(
        None,
        description="กรองประเภทเงิน — null = 1–6",
    )


class IndicatorExportFilterMeta(IndicatorFilterMeta):
    """filter meta ของ export — รวม optional filters ที่ส่งมา."""

    province_ids: list[int] | None = Field(
        None,
        description="กรอง effective_province — null = ไม่กรองจังหวัด",
    )
    type_money_category_ids: list[int] | None = Field(
        None,
        description="กรองประเภทเงิน — null = 1–6",
    )
    regulation_ids: list[int] | None = Field(
        None,
        description="กรองระเบียบ — null = ทุกระเบียบ",
    )


class IndicatorApproverSdshvItem(BaseModel):
    """ยอดแยกตามผู้อนุมัติ (approve_case.user_sdshv)."""

    user_sdshv: str | None = Field(
        None,
        description="ผู้อนุมัติจาก approve_case.user_sdshv — null = ไม่ระบุ",
    )
    case_count: int = Field(..., ge=0)
    total_money_amount: Decimal = Field(..., ge=0)


class IndicatorRegulationBreakdownItem(BaseModel):
    """ยอดแยกตามระเบียบเงิน ภายใต้ประเภทเงิน."""

    regulation_id: int | None = Field(None, description="รหัสระเบียบ — null = ไม่มี regulation_choice")
    regulation_name: str | None = None
    regulation_short_name: str | None = None
    case_count: int = Field(..., ge=0)
    total_money_amount: Decimal = Field(..., ge=0)
    by_approver_sdshv: list[IndicatorApproverSdshvItem] = Field(default_factory=list)


class IndicatorMoneyItem(BaseModel):
    type_money_category_id: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=255)
    name_acronym: str = Field(..., min_length=1, max_length=255)
    name_acrovym_eng: str = Field(..., min_length=1, max_length=255)
    case_count: int = Field(..., ge=0)
    total_money_amount: Decimal = Field(..., ge=0)
    by_regulation: list[IndicatorRegulationBreakdownItem] = Field(
        default_factory=list,
        description="แยกระเบียบเงิน + ผู้อนุมัติ approve_case.user_sdshv",
    )


class IndicatorTotals(BaseModel):
    case_count: int = Field(..., ge=0)
    total_money_amount: Decimal = Field(..., ge=0)


class IndicatorProvinceItem(BaseModel):
    """แถวต่อจังหวัด — ไม่แยกประเภทเงิน (ใช้ใน nationwide)."""

    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    case_count: int = Field(..., ge=0)
    total_money_amount: Decimal = Field(..., ge=0)


class IndicatorExportHouseholdMemberItem(BaseModel):
    """สมาชิกครัวเรือนหนึ่งคนใน export (ไม่รวมผู้ประสบปัญหา)."""

    seq: int = Field(..., description="ลำดับสมาชิกในครัวเรือน")
    prefix_name: str | None = Field(
        None,
        description="coalesce(nullif(prefix_other,''), prefix_type.name)",
    )
    first_name: str
    last_name: str
    cid: str | None = Field(
        None,
        description="เลขบัตรประจำตัวประชาชนจาก household_members.national_id",
    )
    date_of_birth: str | None = Field(
        None,
        description="วันเกิดข้อความไทย เช่น 5 ก.พ. 2569 (ปี พ.ศ. = ค.ศ. + 543)",
    )
    age: int | None = Field(
        None,
        description="ปีจาก date_part('year', age(date_of_birth)) — null ถ้าว่าง",
    )
    relation_name: str | None = None
    occupation: str | None = Field(
        None,
        description="coalesce(occupation, occupation_types.name)",
    )
    monthly_income: str | None = Field(
        None,
        description="รายได้/เดือน รูปแบบ 5,000.00",
    )
    physical_condition: str | None = Field(
        None,
        description="ปกติ | พิการ | เจ็บป่วยเรื้อรัง (จาก normal/disabled/chronic_illness)",
    )
    self_care: str | None = Field(
        None,
        description="ได้ | ไม่ได้ (จาก self_care true/false)",
    )


class IndicatorExportCaseItem(BaseModel):
    """แถวแบนต่อเคส (dossier ครบ 10 กลุ่ม) สำหรับ FE map เข้าเทมเพลต Excel.

    ไม่ส่ง: ลำดับ (FE ใส่จาก index), จำนวนเงินที่ขอ (ไม่มีคอลัมน์ใน DB).
    """

    # --- 1. ทั่วไป ---
    applicant_id: int
    case_channel: str = Field(
        default="พม.CARE",
        description="ที่มาคำร้อง — ค่าคงที่",
    )
    case_number: str | None = None
    notified_at: str | None = Field(
        None,
        description="วันรับแจ้งข้อความไทย เช่น 5 ก.พ. 2569 จาก applicants.created_at (เวลาไทย)",
    )

    # --- 2. รายละเอียดคำร้อง ---
    is_emergency: bool | None = None
    is_existing_case: bool | None = None
    existing_case_source: str | None = None

    # --- 3. ผู้ประสบปัญหา ---
    prefix_name: str | None = Field(
        None,
        description="คำนำหน้าจาก prefix_type.name",
    )
    first_name: str
    last_name: str
    cid: str
    gender: str | None = None
    birth_date: str = Field(
        ...,
        description="วันเกิดข้อความไทย เช่น 5 ก.พ. 2569 (ปี พ.ศ. = ค.ศ. + 543)",
    )
    age: int | None = None
    mobile_phone: str | None = None
    home_phone: str | None = None
    fax_number: str | None = None
    email_address: str | None = None
    is_government_officer: bool | None = None
    requester_relation_name: str | None = None
    marital_status_name: str | None = None
    house_number: str | None = None
    house_moo: str | None = None
    alley: str | None = None
    road: str | None = None
    sub_district_name: str | None = None
    district_name: str | None = None
    address_province_id: int
    address_province_name: str
    effective_province_id: int
    effective_province_name: str
    latitude: str | None = None
    longitude: str | None = None
    address_full: str | None = Field(
        None,
        description="ที่อยู่รวมจากชิ้นส่วน (คำนวณใน Python สำหรับ Excel)",
    )

    # --- 4. เศรษฐกิจ ---
    occupation: str | None = None
    monthly_income: str | None = Field(
        None,
        description="รายได้ผู้ประสบปัญหา/เดือน รูปแบบ 5,000.00",
    )
    family_occupation: str | None = None
    household_member_count: int | None = Field(
        None,
        ge=0,
        description="จำนวนสมาชิกครัวเรือน ไม่รวมผู้ประสบปัญหา (= len(household_members))",
    )
    housing_type_name: str | None = None
    housing_shelter: str | None = None
    housing_rent: str | None = Field(
        None,
        description="ค่าเช่า/เดือน รูปแบบ 5,000.00",
    )
    income_source_names: str | None = Field(
        None,
        description="string_agg ชื่อแหล่งรายได้ (+ other_details) คั่น '; '",
    )

    # --- 5. สมาชิก / อุปการะ ---
    dependency_summary: str | None = Field(
        None,
        description="string_agg ประเภทภาระอุปการะ (+ other) คั่น '; '",
    )
    household_members: list[IndicatorExportHouseholdMemberItem] = Field(
        default_factory=list,
        description=(
            "สมาชิกครัวเรือนเรียง seq ASC "
            "(ไม่รวมแถวที่เป็นผู้ประสบปัญหา — match cid หรือชื่อ-นามสกุล); "
            "ไม่มีสมาชิก → []"
        ),
    )

    # --- 6. สวัสดิการเคยได้รับ ---
    has_received_welfare: bool | None = None
    received_count: int | None = None
    total_received_amount: str | None = Field(
        None,
        description="รวมสวัสดิการที่เคยได้รับ รูปแบบ 5,000.00",
    )
    received_welfare_type_names: str | None = None

    # --- 7. ปัญหา / ความต้องการ ---
    family_distress: str | None = None
    problem_details: str | None = None
    help_request_summary: str | None = None
    request_in_kind_text: str | None = None
    request_other_text: str | None = None

    # --- 8. การพิจารณา ---
    type_money_category_id: int | None = None
    type_money_name: str | None = None
    type_money_name_acronym: str | None = None
    intake_type_money_name: str | None = Field(
        None,
        description="อุดหนุน/เฉพาะกิจ จาก case_handling.type_money — ไม่ชน type_money_category",
    )
    regulation_id: int | None = None
    regulation_name: str | None = None
    regulation_short_name: str | None = None
    help_kind: str | None = None
    money_amount: str | None = Field(
        None,
        description="จำนวนเงินที่ช่วยเหลือ รูปแบบ 5,000.00",
    )
    diagnosis_text: str | None = None
    aided_at: datetime | None = None

    # --- 9. จ่ายเงิน (case_payment) ---
    payment_method_name: str | None = None
    receive_mode: str | None = None
    payee_full_name: str | None = None
    payee_cid: str | None = None
    payee_mobile: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    account_name: str | None = None
    bank_branch: str | None = None

    # --- 10. นักสังคม ---
    sw_user_sdshv: str | None = None
    sw_name: str | None = None
    sw_position: str | None = None
    sw_license_sdshv: str | None = Field(
        None,
        description="coalesce(diagnosis.owner_sdshv, case_handling.sw_user_sdshv)",
    )

    # --- 11. หน่วยงาน (ตัวกรอง พม Smart) ---
    aided_org_sdshv: str | None = Field(
        None,
        description="SDSHV ผู้วินิจฉัยล่าสุด (หน่วยงานที่ช่วยเหลือ)",
    )
    aided_org_name: str | None = Field(
        None,
        description="ชื่อหน่วยงาน snapshot จาก case_diagnosis.owner_organization",
    )
    forward_sdshv: str | None = Field(
        None,
        description="SDSHV คนกดส่งต่อกระทรวงล่าสุด (send_data.send_by_sdshv)",
    )
    disburse_sdshv: str | None = Field(
        None,
        description="SDSHV ผู้เบิกจ่ายล่าสุด (welfare_payment.user_sdshv)",
    )
    responsible_division_id: int | None = Field(
        None,
        description="หน่วยงานที่รับผิดชอบ จาก case_handling.responsible_division_id",
    )
    responsible_division_name: str | None = Field(
        None,
        description="ชื่อหน่วยงานรับผิดชอบ จาก DWF division master",
    )


class IndicatorsByProvinceResponse(BaseModel):
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    budget_year: int = Field(..., description="ปีงบประมาณ พ.ศ.")
    fiscal_start: datetime
    fiscal_end: datetime
    filter: IndicatorFilterMeta
    items: list[IndicatorMoneyItem]
    totals: IndicatorTotals


class IndicatorsNationwideResponse(BaseModel):
    budget_year: int = Field(..., description="ปีงบประมาณ พ.ศ.")
    province_ids: list[int] | None = Field(
        None,
        description="จังหวัดที่กรอง — null = ครบทุกจังหวัดใน master",
    )
    fiscal_start: datetime
    fiscal_end: datetime
    filter: IndicatorNationwideFilterMeta
    items: list[IndicatorProvinceItem]
    totals: IndicatorTotals


class IndicatorsExportResponse(BaseModel):
    budget_year: int = Field(..., description="ปีงบประมาณ พ.ศ.")
    fiscal_start: datetime
    fiscal_end: datetime
    filter: IndicatorExportFilterMeta
    items: list[IndicatorExportCaseItem]
    totals: IndicatorTotals


class IndicatorProvinceOverviewFilterMeta(IndicatorFilterMeta):
    """filter meta ของ province-overview — case_status มีผลเฉพาะยอดเงิน."""

    province_ids: list[int] | None = Field(
        None,
        description="กรอง effective_province — null = ไม่กรองจังหวัด",
    )
    regulation_ids: list[int] | None = Field(
        None,
        description="กรองระเบียบ — null = ทุกระเบียบ",
    )


class IndicatorProvinceOverviewItem(BaseModel):
    """แถวต่อจังหวัด — สรุป 4 ตัวเลข (นับเคส 3 + ยอดเงิน 1)."""

    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    total_budget_amount: Decimal = Field(..., ge=0)
    pending_service_case_count: int = Field(..., ge=0)
    disbursement_case_count: int = Field(..., ge=0)
    aided_case_count: int = Field(..., ge=0)


class IndicatorProvinceOverviewTotals(BaseModel):
    """ยอดรวม 4 ตัวเลขของ province-overview."""

    total_budget_amount: Decimal = Field(..., ge=0)
    pending_service_case_count: int = Field(..., ge=0)
    disbursement_case_count: int = Field(..., ge=0)
    aided_case_count: int = Field(..., ge=0)


class IndicatorsProvinceOverviewResponse(BaseModel):
    budget_year: int = Field(..., description="ปีงบประมาณ พ.ศ. — มีผลเฉพาะยอดเงิน")
    fiscal_start: datetime
    fiscal_end: datetime
    filter: IndicatorProvinceOverviewFilterMeta
    items: list[IndicatorProvinceOverviewItem]
    totals: IndicatorProvinceOverviewTotals
