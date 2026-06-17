"""Pydantic response models ของ dashboard-service."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DashboardStatusCount(BaseModel):
    """จำนวนคำร้องของ 1 current_status — ใช้ทำ donut chart ฝั่งหน้าบ้าน."""

    current_status_id: int
    label: str = Field(..., description="current_status.description_staff")
    color: str
    count: int = Field(..., ge=0)
    percent: float = Field(..., ge=0, le=100, description="round 1 ตำแหน่งทศนิยม")


class DashboardOverviewRead(BaseModel):
    province_id: int
    province_name: str
    total: int = Field(..., ge=0)
    updated_at: datetime
    statuses: list[DashboardStatusCount]


class DashboardDistrictRow(BaseModel):
    """แถวของ 1 อำเภอ — `status_counts` คีย์เป็น current_status_id (string เพราะเป็น JSON key)."""

    district_id: int
    district_name: str
    status_counts: dict[str, int]
    total: int = Field(..., ge=0)


class DashboardDistrictsRead(BaseModel):
    province_id: int
    province_name: str
    page: int
    page_size: int
    total_items: int = Field(..., description="จำนวนอำเภอทั้งหมดในจังหวัด (ไม่ใช่จำนวนคำร้อง)")
    total_pages: int
    items: list[DashboardDistrictRow]


class DashboardNationalOverviewRead(BaseModel):
    total: int = Field(..., ge=0)
    updated_at: datetime
    statuses: list[DashboardStatusCount]


class DashboardProvinceRow(BaseModel):
    province_id: int
    province_name: str
    status_counts: dict[str, int]
    total: int = Field(..., ge=0)


class DashboardProvincesRead(BaseModel):
    page: int
    page_size: int
    total_items: int = Field(..., description="จำนวนจังหวัดทั้งหมด (ไม่ใช่จำนวนคำร้อง)")
    total_pages: int
    items: list[DashboardProvinceRow]


class DashboardSubDistrictRow(BaseModel):
    sub_district_id: int
    sub_district_name: str
    status_counts: dict[str, int]
    total: int = Field(..., ge=0)


class DashboardSubDistrictsRead(BaseModel):
    district_id: int
    district_name: str
    province_id: int
    province_name: str
    page: int
    page_size: int
    total_items: int = Field(..., description="จำนวนตำบลทั้งหมดในอำเภอ (ไม่ใช่จำนวนคำร้อง)")
    total_pages: int
    items: list[DashboardSubDistrictRow]
