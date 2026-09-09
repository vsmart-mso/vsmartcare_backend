"""Schemas ของ `/v1/liveness/*` — ด่านยืนยันตัวตนด้วยใบหน้า (AINU eKYC)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..models.liveness_attempt import CLIENT_SKIP_REASONS


class LivenessSdkConfig(BaseModel):
    """ค่าที่ frontend ส่งต่อเข้า AinuEkyc.setup() ตรง ๆ (ชื่อฟิลด์เป็น camelCase ตาม SDK)"""

    account_id: str = Field(serialization_alias="accountId")
    account_secret: str = Field(serialization_alias="accountSecret")
    flow_id: str = Field(serialization_alias="flowId")
    language: str = Field(serialization_alias="language")
    reference_id: str = Field(serialization_alias="referenceId")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class LivenessSessionResponse(BaseModel):
    reference_id: str
    status: str
    config: LivenessSdkConfig


class LivenessTransactionRequest(BaseModel):
    """transaction_id จาก onReady() — เก็บทันทีเพื่อให้ตามเรื่องกับ AINU ได้แม้ผู้ใช้เลิกกลางคัน"""

    transaction_id: str = Field(min_length=1, max_length=128)


class LivenessResultRequest(BaseModel):
    """payload ดิบจาก onEkycResult() — เก็บทั้งก้อนไม่ตัดอะไร"""

    payload: dict[str, Any]


class LivenessSkipRequest(BaseModel):
    """เมื่อ "เรา" เป็นคนสรุปว่าใช้ระบบไม่ได้ — คนละเรื่องกับ AINU ตอบว่าสแกนไม่ผ่าน"""

    skip_reason: str = Field(
        description="รหัสของเราเอง: " + " / ".join(sorted(CLIENT_SKIP_REASONS)),
    )


class LivenessAttemptRead(BaseModel):
    """สิ่งที่ตอบกลับ frontend — ตั้งใจไม่มี raw_payload"""

    reference_id: str
    status: str
    transaction_id: str | None = None
    liveness_reason: str | None = None
    fail_reason: str | None = None
    skip_reason: str | None = None
    description: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
