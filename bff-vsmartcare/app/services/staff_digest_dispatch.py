"""ส่งอีเมลสรุปคำร้องรายวัน (staff digest) ผ่าน notification-service."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

StaffDigestRole = Literal["social_worker", "pmj", "finance"]

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
        {
            "external_user_id": "dev-pmj-1",
            "email": "pmj@example.test",
            "full_name": "นางทดสอบ พมจ",
            "position": "พมจ.",
            "province_id": 10,
            "roles": ["pmj"],
        },
        {
            "external_user_id": "dev-fin-1",
            "email": "finance@example.test",
            "full_name": "นายทดสอบ การเงิน",
            "position": "เจ้าหน้าที่การเงิน",
            "province_id": 10,
            "roles": ["finance"],
        },
    ],
}

ROLE_HIGHLIGHT_LABEL: dict[StaffDigestRole, str] = {
    "social_worker": "รอรับเรื่อง",
    "pmj": "รออนุมัติ",
    "finance": "รอเบิก",
}

ROLE_SUMMARY_FIELD: dict[StaffDigestRole, str] = {
    "social_worker": "social_worker_pending",
    "pmj": "pmj_pending_approve",
    "finance": "finance_pending",
}

TEMPLATE_CODE = "STAFF_CASE_STATUS_DIGEST"


class StaffDigestRecipient(BaseModel):
    external_user_id: str = Field(..., min_length=1, max_length=255, examples=["dev-sw-1"])
    email: str = Field(..., min_length=3, max_length=255, examples=["user@example.test"])
    full_name: str = Field(..., min_length=1, max_length=255, examples=["นายทดสอบ นักสังคม"])
    position: str = Field(default="", max_length=255, examples=["นักสังคมสงเคมชนชั้นกลาง"])
    province_id: int = Field(..., ge=1, examples=[10])
    roles: list[StaffDigestRole] = Field(
        ...,
        min_length=1,
        description="ต้องเป็น social_worker | pmj | finance เท่านั้น (ไม่ใช่ชื่อภาษาไทย)",
        examples=[["social_worker"]],
    )


class StaffDigestRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [_STAFF_DIGEST_REQUEST_EXAMPLE]},
    )

    digest_date: date = Field(
        ...,
        description="รูปแบบ YYYY-MM-DD เท่านั้น (เช่น 2026-05-21)",
        examples=["2026-05-21"],
    )
    skip_if_all_zero: bool = Field(
        default=True,
        description="true = ข้ามผู้รับเมื่อตัวเลขของทุก role ใน roles เป็น 0",
    )
    recipients: list[StaffDigestRecipient] = Field(..., min_length=1)


class StaffDigestDispatchResult(BaseModel):
    digest_date: date
    sent: list[dict[str, Any]] = Field(default_factory=list)
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


def _highlight_count_for_role(summary: dict[str, Any], role: StaffDigestRole) -> int:
    field = ROLE_SUMMARY_FIELD[role]
    return int(summary.get(field) or 0)


def _role_counts_all_zero(summary: dict[str, Any], roles: list[StaffDigestRole]) -> bool:
    return all(_highlight_count_for_role(summary, role) == 0 for role in roles)


def _build_notification_payload(
    *,
    recipient: StaffDigestRecipient,
    role: StaffDigestRole,
    summary: dict[str, Any],
    digest_date: date,
    tracking_url: str,
) -> dict[str, Any]:
    highlight_count = _highlight_count_for_role(summary, role)
    return {
        "staff_name": recipient.full_name,
        "full_name": recipient.full_name,
        "position": recipient.position,
        "province_name": summary.get("province_name") or "",
        "digest_date": digest_date.isoformat(),
        "highlight_label": ROLE_HIGHLIGHT_LABEL[role],
        "highlight_count": highlight_count,
        "social_worker_pending": summary.get("social_worker_pending", 0),
        "pmj_pending_approve": summary.get("pmj_pending_approve", 0),
        "finance_pending": summary.get("finance_pending", 0),
        "total_applicants": summary.get("total_applicants", 0),
        "tracking_url": tracking_url,
        "role": role,
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
                    "reason": "all_role_counts_zero",
                }
            )
            continue

        idempotency_key = f"staff-digest-{body.digest_date.isoformat()}-{recipient.external_user_id}"
        primary_role = recipient.roles[0]
        payload = _build_notification_payload(
            recipient=recipient,
            role=primary_role,
            summary=summary,
            digest_date=body.digest_date,
            tracking_url=tracking_url,
        )

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
        sent=sent,
        skipped=skipped,
        errors=errors,
    )
