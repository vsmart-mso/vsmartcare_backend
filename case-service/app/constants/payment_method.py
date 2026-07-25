"""รหัส master payment_method — ใช้ร่วมกับ case_payment / KTB / cash disbursement."""

from __future__ import annotations

from typing import Any

CASH_METHOD_ID = 1
CHEQUE_METHOD_ID = 2
CASH_OR_CHEQUE_IDS = frozenset({CASH_METHOD_ID, CHEQUE_METHOD_ID})

BANK_CLEAR_FIELDS = (
    "account_number",
    "account_name",
    "bank_name_id",
    "bank_branch",
    "bank_account_type_id",
)


def normalize_payment_method_id(method_id: Any) -> int | None:
    if method_id is None or method_id is False:
        return None
    try:
        return int(str(method_id).strip())
    except (TypeError, ValueError):
        return None


def is_cash_or_cheque(method_id: Any) -> bool:
    return normalize_payment_method_id(method_id) in CASH_OR_CHEQUE_IDS


def payment_hides_bank(method_id: Any, *, method_code: str | None = None) -> bool:
    """Cash/cheque — และ PromptPay (legacy_vsmart_value=1 / code=promptpay) ไม่บังคับบัญชี."""
    if is_cash_or_cheque(method_id):
        return True
    code = (method_code or "").strip().lower()
    return code == "promptpay"


def payment_requires_ktb_gate(
    method_id: Any,
    *,
    method_code: str | None = None,
    requires_ktb_form: bool | None = None,
) -> bool:
    """
    True เมื่อวิธีจ่ายอาจต้องมีหลักฐาน KTB.
    Unknown/empty method → True (เข้มจนกว่าจะรู้วิธีจ่าย).
    """
    mid = normalize_payment_method_id(method_id)
    if mid is None:
        return True
    if payment_hides_bank(method_id, method_code=method_code):
        return False
    if requires_ktb_form is False:
        return False
    return True


def clear_bank_fields_in_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return payload
    for key in BANK_CLEAR_FIELDS:
        payload[key] = None
    return payload
