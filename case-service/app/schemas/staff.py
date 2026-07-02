"""Schemas สำหรับ staff API (HI-01)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StaffLoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=255)


class StaffTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="อายุ token (วินาที)")
    province_id: int
    display_name: str = ""
