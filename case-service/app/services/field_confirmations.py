"""Validate + apply citizen field confirmations on resubmit (TASK_211)."""

from __future__ import annotations

from datetime import datetime, timezone

from ..models.review import WelfareReviewComment
from ..schemas.review import FieldConfirmationItem

# ฟิลด์ที่ไม่บังคับยืนยัน — สอดคล้อง EditRequestPage (FE)
_SKIP_CONFIRM_FIELD_NAMES = frozenset({
    "remarks",
    "doc_ktb_corporate",
    "requested_assistance_money",
})


def required_confirm_field_ids(
    comments: list[WelfareReviewComment],
) -> set[int]:
    """review_field_id ที่ประชาชนต้องยืนยันก่อน resubmit."""
    required: set[int] = set()
    for comment in comments:
        field = comment.review_field
        if field is None:
            continue
        if field.name in _SKIP_CONFIRM_FIELD_NAMES:
            continue
        required.add(comment.review_field_id)
    return required


def validate_field_confirmations(
    comments: list[WelfareReviewComment],
    confirmations: list[FieldConfirmationItem] | None,
) -> str | None:
    """ตรวจ payload ยืนยัน — คืน error detail string หรือ None ถ้าผ่าน.

    Error codes:
    - field_confirmations_required
    - field_confirmations_incomplete
    - field_confirmations_invalid_field
    """
    required = required_confirm_field_ids(comments)

    # ไม่มีฟิลด์ที่ต้องยืนยัน (เช่น เหลือแค่ remarks / money) → ไม่บังคับ body
    if not required:
        return None

    if not confirmations:
        return "field_confirmations_required"

    submitted = {item.review_field_id for item in confirmations}

    if not required.issubset(submitted):
        return "field_confirmations_incomplete"

    if not submitted.issubset(required):
        return "field_confirmations_invalid_field"

    return None


def apply_field_confirmations(
    comments: list[WelfareReviewComment],
    confirmations: list[FieldConfirmationItem],
    *,
    confirmed_at: datetime | None = None,
) -> None:
    """เขียน citizen_confirmed_at / citizen_confirmation_type ลง comment rows."""
    type_by_field = {
        item.review_field_id: item.confirmation_type for item in confirmations
    }
    now = confirmed_at or datetime.now(timezone.utc)
    required = required_confirm_field_ids(comments)

    for comment in comments:
        if comment.review_field_id not in required:
            continue
        conf_type = type_by_field.get(comment.review_field_id)
        if conf_type is None:
            continue
        comment.citizen_confirmed_at = now
        comment.citizen_confirmation_type = conf_type
