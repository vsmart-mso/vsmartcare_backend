"""สคีมารายการคำร้องสำหรับหน้าจอเจ้าหน้าที่."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .address import AddressRead
from .applicant import ApplicantRead
from .dependency import DependencyLoadRead
from .economic import EconomicInfoRead
from .person import PersonRead
from .status_log import WelfareRequestStatusRead
from .welfare import (
    WelfareEvidenceRead,
    WelfareHistoryDetailRead,
    WelfareHistoryRead,
    WelfareRequestTypeRead,
)


class CaseForStaffRead(BaseModel):
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


class CaseForStaffListResponse(BaseModel):
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    total_applicants: int = Field(..., ge=0, description="จำนวน Applicant ทั้งหมดในจังหวัด")
    filtered_applicants: int = Field(..., ge=0, description="จำนวน Applicant หลังใช้ filter")
    items: list[CaseForStaffRead] = Field(default_factory=list)


class CaseForStaffWelfareRequestStatusCreate(BaseModel):
    """บันทึกสถานะใหม่ใน welfare_request_status (อ้างอิง applicant + current_status)."""

    applicant_id: int = Field(..., ge=1)
    current_status_id: int = Field(..., ge=1)
    remarks: str | None = None
    update_by_sdshv: str | None = Field(None, max_length=255)


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


class CaseForStaffApplicantStaffFieldsRead(BaseModel):
    """ผลลัพธ์หลังอัปเดต type_money_category_id / sw_explorer_sdshv."""

    applicant_id: int
    type_money_category_id: int | None = None
    type_money_name: str | None = Field(None, max_length=255)
    type_money_name_acronym: str | None = Field(None, max_length=255)
    type_money_color: str | None = Field(None, max_length=32)
    sw_explorer_sdshv: str | None = Field(None, max_length=255)
    updated_at: datetime


class PorKor1TypeMoney(BaseModel):
    """ประเภทเงินช่วยเหลือจาก applicants.type_money_category_id + master — ไม่ใช้เมื่อ FK ว่าง."""

    type_money_category_id: int = Field(..., ge=1)
    name: str | None = Field(None, max_length=255)
    name_acronym: str | None = Field(None, max_length=255)
    color: str | None = Field(None, max_length=32)


class PorKor1Summary(BaseModel):
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


class PorKor1WelfareRequestTypeItem(BaseModel):
    """ประเภทคำร้องที่ขอหนึ่งรายการ พร้อมชื่อจาก master."""

    item: WelfareRequestTypeRead
    request_type_name: str | None = Field(None, max_length=255)


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


class PorKor1EvidenceItem(BaseModel):
    """หลักฐานแนบหนึ่งไฟล์ พร้อมชื่อประเภทเอกสารและ path สำหรับ GET รูป."""

    evidence: WelfareEvidenceRead
    attachment_type_name: str | None = Field(None, max_length=255)
    view_path: str = Field(
        ...,
        description="path สำหรับ GET ไฟล์รูป — ต่อกับ base URL ของ case-service หรือ BFF",
    )


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
