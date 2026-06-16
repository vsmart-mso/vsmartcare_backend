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
