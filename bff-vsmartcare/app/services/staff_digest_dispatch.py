"""ส่งอีเมลสรุปคำร้องรายวัน (staff digest) ผ่าน notification-service."""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

StaffDigestRole = Literal["social_worker", "pmj", "finance"]

# ตัวอย่างใน Swagger (Example Value) — เนื้อหาเดียวกับใน STAFF_DIGEST.md
_STAFF_DIGEST_REQUEST_EXAMPLE = {
    "digest_date": "2026-05-21",
    "skip_if_all_zero": False,
    "recipients": [
        {
            "external_user_id": "dev-sw-1",
            "email": "social.worker@example.test",
            "full_name": "นายทดสอบ นักสังคม",
            "position": "นักสังคมสงเคมชนชั้นกลาง",
            "province_id": 10,
            "roles": ["social_worker"],
        },
    ],
}

ROLE_HIGHLIGHT_LABEL: dict[StaffDigestRole, str] = {
    "social_worker": "รอรับเรื่อง",
    "pmj": "รออนุมัติ",
    "finance": "รอการเบิกจ่าย",
}

ROLE_SUMMARY_FIELD: dict[StaffDigestRole, str] = {
    "social_worker": "social_worker_pending",
    "pmj": "pmj_pending_approve",
    "finance": "finance_pending",
}

ROLE_EMERGENCY_FIELD: dict[StaffDigestRole, str] = {
    "social_worker": "social_worker_emergency",
    "pmj": "pmj_emergency",
    "finance": "finance_emergency",
}

ROLE_EMERGENCY_LABEL: dict[StaffDigestRole, str] = {
    "social_worker": "คำร้องเร่งด่วน (รอรับเรื่อง)",
    "pmj": "คำร้องเร่งด่วน (รออนุมัติ)",
    "finance": "คำร้องเร่งด่วน (รอการเบิกจ่าย)",
}

TEMPLATE_CODE = "STAFF_CASE_STATUS_DIGEST"

# ค่าที่รับจากระบบต้นทาง → บทบาท canonical (เนื้อหาอีเมลไม่ใช้ฟิลด์ position โดยตรง)
_ROLE_ALIASES: dict[str, StaffDigestRole] = {
    "social_worker": "social_worker",
    "socialworker": "social_worker",
    "sw": "social_worker",
    "pmj": "pmj",
    "finance": "finance",
    "นักสังคม": "social_worker",
    "นักสังคมสงเคราะห์": "social_worker",
    "นักสังคมสงเคมชนสงเคราะห์": "social_worker",
    "พมจ": "pmj",
    "พม.จ.": "pmj",
    "พม.": "pmj",
    "ปกครอง": "pmj",
    "การเงิน": "finance",
    "เจ้าหน้าที่การเงิน": "finance",
}


def _normalize_role_token(raw: object) -> StaffDigestRole | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text in _ROLE_ALIASES:
        return _ROLE_ALIASES[text]
    compact = re.sub(r"[\s.]+", "", text).lower()
    return _ROLE_ALIASES.get(compact)


def _infer_role_from_position(position: str) -> StaffDigestRole | None:
    """เดาบทบาทจากตำแหน่งเมื่อ roles ไม่ตรง (เช่น ส่ง position=พมจ แต่ roles ผิด)."""
    p = position.strip()
    if not p:
        return None
    if "การเงิน" in p:
        return "finance"
    if "นักสังคม" in p:
        return "social_worker"
    compact = re.sub(r"[\s.]+", "", p)
    if compact.startswith("พม") or "พมจ" in compact:
        return "pmj"
    return None


def resolve_primary_role(
    *,
    roles: list[StaffDigestRole],
    position: str,
    explicit_role: StaffDigestRole | None = None,
) -> StaffDigestRole:
    """เลือกบทบาทสำหรับเนื้อหาอีเมล — ไม่ใช้แค่ roles[0] ถ้าขัดกับตำแหน่ง."""
    if explicit_role is not None:
        return explicit_role

    inferred = _infer_role_from_position(position)
    if len(roles) == 1:
        sole = roles[0]
        if inferred and inferred != sole:
            logger.info(
                "staff_digest: roles=%s ไม่ตรง position=%r — ใช้บทบาทจากตำแหน่ง %s",
                sole,
                position,
                inferred,
            )
            return inferred
        return sole
    if inferred:
        return inferred
    return roles[0]


class StaffDigestRecipient(BaseModel):
    external_user_id: str = Field(..., min_length=1, max_length=255, examples=["dev-sw-1"])
    email: str = Field(..., min_length=3, max_length=255, examples=["user@example.test"])
    full_name: str = Field(..., min_length=1, max_length=255, examples=["นายทดสอบ นักสังคม"])
    position: str = Field(
        default="",
        max_length=255,
        examples=["นักสังคมสงเคมชนชั้นกลาง"],
        description="แสดงในอีเมลเท่านั้น — ไม่กำหนด bucket; ใช้ role / roles",
    )
    province_id: int = Field(..., ge=1, examples=[10])
    role: StaffDigestRole | None = Field(
        default=None,
        description="บทบาทหลัก (แนะนำ) — ชนะ roles ถ้าระบุ",
        examples=["pmj"],
    )
    roles: list[StaffDigestRole] = Field(
        default_factory=list,
        min_length=0,
        description=(
            "social_worker | pmj | finance หรือชื่อไทย (พมจ, นักสังคม, การเงิน). "
            "ถ้าว่างจะเดาจาก role หรือ position"
        ),
        examples=[["pmj"]],
    )

    @field_validator("role", mode="before")
    @classmethod
    def _normalize_role_field(cls, value: object) -> StaffDigestRole | None:
        if value is None or value == "":
            return None
        mapped = _normalize_role_token(value)
        if mapped is None:
            raise ValueError(
                "role ต้องเป็น social_worker, pmj, finance หรือชื่อไทย (พมจ / นักสังคม / การเงิน)"
            )
        return mapped

    @field_validator("roles", mode="before")
    @classmethod
    def _normalize_roles_field(cls, value: object) -> list[StaffDigestRole]:
        if value is None:
            return []
        items: list[object]
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, list):
            items = value
        else:
            raise ValueError("roles ต้องเป็น string หรือ array")

        mapped: list[StaffDigestRole] = []
        for item in items:
            role = _normalize_role_token(item)
            if role is None:
                raise ValueError(
                    f"roles ไม่รู้จัก: {item!r} — ใช้ social_worker | pmj | finance "
                    "หรือ พมจ / นักสังคม / การเงิน"
                )
            if role not in mapped:
                mapped.append(role)
        return mapped

    @model_validator(mode="after")
    def _require_resolvable_role(self) -> StaffDigestRecipient:
        if self.role is not None:
            return self
        if self.roles:
            return self
        if _infer_role_from_position(self.position) is not None:
            return self
        raise ValueError(
            "ต้องระบุ role หรือ roles (social_worker | pmj | finance) "
            "หรือ position ที่ระบุตำแหน่งชัดเจน (เช่น พมจ, นักสังคมสงเคราะห์)"
        )


class StaffDigestRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": _STAFF_DIGEST_REQUEST_EXAMPLE},
    )

    digest_date: date = Field(
        ...,
        description="วันที่แสดงในอีเมล รูปแบบ YYYY-MM-DD",
        examples=["2026-05-21"],
    )
    idempotency_bucket: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "รอบอ้างอิงจากระบบต้นทาง (บันทึกใน response เท่านั้น — ไม่ใช้กันส่งซ้ำ). "
            "การส่งอีเมลทุกครั้งที่เรียก API จะส่งจริง (idempotency ต่อคำขอ)"
        ),
        examples=["2026-05-21T08"],
    )
    skip_if_all_zero: bool = Field(
        default=False,
        description=(
            "true = ข้ามผู้รับเมื่อตัวเลข bucket ของ role เป็น 0 ทั้งหมด "
            "(ค่าเริ่มต้น false — ส่งอีเมลทุกครั้งที่ระบบต้นทางเรียก)"
        ),
    )
    recipients: list[StaffDigestRecipient] = Field(..., min_length=1)


class StaffDigestDispatchResult(BaseModel):
    digest_date: date
    idempotency_bucket: str = Field(
        ...,
        description="ค่าอ้างอิงจาก request (หรือ fallback digest_date) — ไม่บล็อกการส่งซ้ำ",
    )
    sent: list[dict[str, Any]] = Field(default_factory=list)
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


def resolve_idempotency_bucket(digest_date: date, idempotency_bucket: str | None) -> str:
    """ค่าอ้างอิงรอบจากระบบต้นทาง — ไม่ใช้กันส่งซ้ำที่ notification-service."""
    cleaned = (idempotency_bucket or "").strip()
    return cleaned if cleaned else digest_date.isoformat()


def _count_for_role(summary: dict[str, Any], field: str) -> int:
    return int(summary.get(field) or 0)


def _highlight_count_for_role(summary: dict[str, Any], role: StaffDigestRole) -> int:
    return _count_for_role(summary, ROLE_SUMMARY_FIELD[role])


def _emergency_count_for_role(summary: dict[str, Any], role: StaffDigestRole) -> int:
    return _count_for_role(summary, ROLE_EMERGENCY_FIELD[role])


def _role_counts_all_zero(summary: dict[str, Any], roles: list[StaffDigestRole]) -> bool:
    return all(
        _highlight_count_for_role(summary, role) == 0
        and _emergency_count_for_role(summary, role) == 0
        for role in roles
    )


def _build_notification_payload(
    *,
    recipient: StaffDigestRecipient,
    role: StaffDigestRole,
    summary: dict[str, Any],
    digest_date: date,
    tracking_url: str,
) -> dict[str, Any]:
    highlight_count = _highlight_count_for_role(summary, role)
    emergency_count = _emergency_count_for_role(summary, role)
    return {
        "staff_name": recipient.full_name,
        "full_name": recipient.full_name,
        "position": recipient.position,
        "province_name": summary.get("province_name") or "",
        "total_applicants": int(summary.get("total_applicants") or 0),
        "digest_date": digest_date.isoformat(),
        "role": role,
        "highlight_label": ROLE_HIGHLIGHT_LABEL[role],
        "highlight_count": highlight_count,
        "emergency_label": ROLE_EMERGENCY_LABEL[role],
        "emergency_count": emergency_count,
        "tracking_url": tracking_url,
    }


async def dispatch_staff_digest(
    *,
    case_service_url: str,
    notification_service_url: str,
    frontend_url: str,
    body: StaffDigestRequest,
    post_json: Any,
    get_json: Any,
) -> StaffDigestDispatchResult:
    """ดึง summary ต่อจังหวัด แล้วส่ง notification ตาม roles ของแต่ละ recipient."""
    case_base = case_service_url.rstrip("/")
    notif_base = notification_service_url.rstrip("/")
    cleaned_frontend = frontend_url.strip()
    tracking_url = (
        cleaned_frontend
        if cleaned_frontend.endswith("/")
        else f"{cleaned_frontend}/"
        if cleaned_frontend
        else "http://localhost:5173/"
    )

    province_ids = {r.province_id for r in body.recipients}
    summaries: dict[int, dict[str, Any]] = {}
    for province_id in province_ids:
        summaries[province_id] = await get_json(
            f"{case_base}/v1/case_for_staff/status-summary?province_id={province_id}"
        )

    bucket = resolve_idempotency_bucket(body.digest_date, body.idempotency_bucket)

    sent: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for recipient in body.recipients:
        summary = summaries.get(recipient.province_id)
        if summary is None:
            errors.append(
                {
                    "external_user_id": recipient.external_user_id,
                    "email": recipient.email,
                    "detail": "province_summary_missing",
                }
            )
            continue

        if body.skip_if_all_zero and _role_counts_all_zero(summary, recipient.roles):
            skipped.append(
                {
                    "external_user_id": recipient.external_user_id,
                    "email": recipient.email,
                    "province_id": recipient.province_id,
                    "reason": "recipient_role_counts_zero",
                }
            )
            continue

        primary_role = resolve_primary_role(
            roles=recipient.roles,
            position=recipient.position,
            explicit_role=recipient.role,
        )
        payload = _build_notification_payload(
            recipient=recipient,
            role=primary_role,
            summary=summary,
            digest_date=body.digest_date,
            tracking_url=tracking_url,
        )
        idempotency_key = f"staff-digest-{uuid4().hex}"

        try:
            result = await post_json(
                f"{notif_base}/v1/notifications",
                {
                    "idempotency_key": idempotency_key,
                    "channel": "email",
                    "to": recipient.email,
                    "template_code": TEMPLATE_CODE,
                    "payload": payload,
                },
            )
            sent.append(
                {
                    "external_user_id": recipient.external_user_id,
                    "email": recipient.email,
                    "role": primary_role,
                    "highlight_count": payload["highlight_count"],
                    "emergency_count": payload["emergency_count"],
                    "idempotency_key": idempotency_key,
                    "idempotency_bucket": bucket,
                    "notification": result,
                }
            )
        except HTTPException as exc:
            errors.append(
                {
                    "external_user_id": recipient.external_user_id,
                    "email": recipient.email,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {
                    "external_user_id": recipient.external_user_id,
                    "email": recipient.email,
                    "detail": str(exc),
                }
            )

    return StaffDigestDispatchResult(
        digest_date=body.digest_date,
        idempotency_bucket=bucket,
        sent=sent,
        skipped=skipped,
        errors=errors,
    )
