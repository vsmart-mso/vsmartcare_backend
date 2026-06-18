"""สคีมาแดชบอร์ด — สอดคล้องกับ dashboard-service `app/schemas.py`."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DashboardStatusCount(BaseModel):
    current_status_id: int
    label: str
    color: str
    count: int = Field(..., ge=0)
    percent: float = Field(..., ge=0, le=100)


class DashboardOverviewRead(BaseModel):
    province_id: int
    province_name: str
    total: int = Field(..., ge=0)
    updated_at: datetime
    statuses: list[DashboardStatusCount]


class DashboardDistrictRow(BaseModel):
    district_id: int
    district_code: str | None = None
    district_name: str
    status_counts: dict[str, int]
    total: int = Field(..., ge=0)


class DashboardDistrictsRead(BaseModel):
    province_id: int
    province_name: str
    page: int
    page_size: int
    total_items: int
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
    total_items: int
    total_pages: int
    items: list[DashboardProvinceRow]


class DashboardSubDistrictRow(BaseModel):
    sub_district_id: int
    sub_district_code: str | None = None
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
    total_items: int
    total_pages: int
    items: list[DashboardSubDistrictRow]
