"""ตรวจสอบรายใหม่ / รายเดิมจากเลขบัตรประชาชน (vcare_main, MSO logbook, vsmart_main).

เป้าหมาย
--------
ตอบว่า CID นี้เป็น **รายเดิม** (`is_existing_case=true`) หรือ **รายใหม่** (`false`)
โดยเช็คแหล่งที่เปิดใช้งานพร้อมกัน แล้วรวมผล — ถ้าแหล่งใดแหล่งหนึ่งที่ตรวจได้พบข้อมูล ถือเป็นรายเดิม

แหล่งข้อมูลและข้อมูลสำหรับ ``applicant_submission_audit``
-----------------------------------------------------------
- ``vcare_main`` (VCARE) — คืน ``detail.prior_case`` (จังหวัด/บัญชี/ref จากเคสล่าสุด)
  และ ``detail.submission_audit`` แบบเดียวกับ ``vsmart_main``: จากแถว
  ``applicant_submission_audit`` ถ้ามี หรือสังเคราะห์จาก prior (``existing_case_source=VCARE``)
  ถ้ายังไม่มีแถว audit จะ fallback จังหวัดจากที่อยู่ + เลขบัญชีจาก ``applicants``

- ``vsmart_main`` (Legacy vSmart) — ไม่มีตาราง audit ใน Legacy แต่ API ``check-cid``
  คืน ``prior_case`` (จังหวัด / เลขบัญชี / informer_id) ซึ่ง map เป็น ``detail.submission_audit``
  ในฟิลด์เดียวกับ ``applicant_submission_audit``

- ``mso_logbook`` (Welfare / logbook) — บอกได้แค่ **รายใหม่หรือรายเดิม** (``found``)
  **ไม่** คืน ``prior_case`` / ``submission_audit`` (ไม่มี snapshot สำหรับ Require KTB)

แหล่งข้อมูล (สรุป)
-------------------
- ``vcare_main`` — ฐาน VCARE (case-service): มี ``applicants`` ของ ``persons`` ที่ cid ตรงกัน
- ``mso_logbook`` — API ภายนอก MSO logbook (ตั้ง ``MSO_LOGBOOK_*`` ใน .env)
- ``vsmart_main``   — API ภายนอก VSmart หลัก (ตั้ง ``VSMART_MAIN_*`` ใน .env)

การใช้งาน (HTTP)
----------------
::

    GET /v1/check-case?cid=1103701234561

การใช้งาน (เรียกจากโค้ด)
-------------------------
::

    from app.api.check_case import check_existing_case_by_cid

    result = await check_existing_case_by_cid(session, cid)

``POST /v1/cases`` เรียกฟังก์ชันนี้ก่อนบันทึก applicant แล้วตั้ง ``is_existing_case`` ให้อัตโนมัติ

ตั้งค่า .env (case-service)
---------------------------
::

    # เปิด/ปิดแหล่งตรวจ (default true) — false = ข้ามแหล่งนั้น
    CHECK_CASE_ENABLE_VCARE_SELF=true
    CHECK_CASE_ENABLE_MSO_LOGBOOK=true

    MSO_LOGBOOK_URL=https://volunteer-smart-beta.nu.ac.th/vapi/api-convert/logbook/get-problem/
    MSO_LOGBOOK_API_KEY=your-api-key

    VSMART_MAIN_BASE_URL=https://vsmart.example.go.th
    VSMART_MAIN_CHECK_PATH=/api/v1/people/check-cid
    VSMART_MAIN_API_KEY=secret

    EXTERNAL_CHECK_TIMEOUT_SECONDS=10

ถ้าไม่ตั้ง ``*_BASE_URL`` แหล่งนั้นจะ ``available=false`` (ไม่นับใน ``is_existing_case``)
ถ้าตั้ง ``CHECK_CASE_ENABLE_*=false`` แหล่งนั้นจะ ``message=disabled``

ความหมาย ``sources[]``
-----------------------
- ``found``     — พบข้อมูลในระบบนั้น (ใช้เมื่อ ``available=true``)
- ``available`` — ตรวจสอบสำเร็จ; ``false`` = ปิด config / ไม่ได้ตั้ง URL / timeout / error
- ``message``   — สรุปสั้น ๆ เช่น ``not_found``, ``found``, ``disabled``, ``not_configured``, ``timeout``
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.citizen_security import CitizenClaims, assert_cid_owner, require_citizen
from ..core.database import get_session
from ..models.applicant import Applicant
from ..models.person import Person
from ..schemas.check_case import CheckCaseSource, ExistingCaseCheckResult, SourceCheckResult
from ..schemas.person import validate_thai_cid
from ..services.ktb_requirement import (
    finalize_detail_submission_audit,
    fetch_vcare_prior_case_detail,
)
from ..settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/check-case", tags=["check_case"])

_BOOL_KEYS = (
    "exists",
    "found",
    "is_existing",
    "is_existing_case",
    "has_record",
    "has_data",
    "has_case",
)
_COUNT_KEYS = ("count", "total", "total_count")
_LIST_KEYS = ("data", "items", "results", "records", "cases", "petitions")


def _dig_value(payload: Any, keys: tuple[str, ...]) -> Any:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def _parse_prior_case_from_payload(payload: Any) -> dict[str, Any] | None:
    """ดึง prior_case จาก response ภายนอก (Legacy prior_case หรือ MSO get-problem)."""
    if not isinstance(payload, dict):
        return None

    nested = payload.get("prior_case")
    if isinstance(nested, dict):
        root = nested
    else:
        root = payload
        for wrap_key in ("data", "Data", "result"):
            inner = payload.get(wrap_key)
            if isinstance(inner, dict):
                root = inner
                break

    province_id = _dig_value(root, ("province_id", "provinceId", "cm_province_id"))
    if province_id is not None:
        try:
            province_id = int(province_id)
        except (TypeError, ValueError):
            province_id = None

    ref_raw = _dig_value(
        root,
        ("ref_id", "informer_id", "applicant_id", "problem_id", "logbook_id", "id"),
    )
    ref_id: int | None = None
    if ref_raw is not None:
        try:
            ref_id = int(ref_raw)
        except (TypeError, ValueError):
            ref_id = None

    province_name = _dig_value(root, ("province_name", "provinceName", "cm_province", "province"))
    if province_name is not None:
        province_name = str(province_name).strip() or None

    bank_account_no = _dig_value(
        root,
        ("bank_account_no", "account_number", "account_no"),
    )
    if bank_account_no is None:
        payee_bank = root.get("payee_detail_bank")
        if isinstance(payee_bank, dict):
            bank_account_no = payee_bank.get("account_number") or payee_bank.get("account_no")
    if bank_account_no is not None:
        bank_account_no = str(bank_account_no).strip() or None

    if (
        province_id is None
        and not province_name
        and ref_id is None
        and not bank_account_no
    ):
        return None

    prior: dict[str, Any] = {
        "ref_id": ref_id,
        "province_id": province_id,
        "province_name": province_name,
        "bank_account_no": bank_account_no,
    }
    if ref_id is not None and "informer_id" not in prior:
        prior["informer_id"] = ref_id
    return prior


def _merge_detail_with_prior(
    detail: dict[str, Any] | None,
    prior: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if prior is None:
        return detail
    merged = dict(detail or {})
    merged["prior_case"] = prior
    return merged


def _normalize_cid(cid: str) -> str:
    return validate_thai_cid(cid.strip())


def _disabled_source_result(source: CheckCaseSource) -> SourceCheckResult:
    return SourceCheckResult(
        source=source,
        found=False,
        available=False,
        message="disabled",
    )


def _json_indicates_existing(payload: Any) -> bool | None:
    if payload is None:
        return None
    if isinstance(payload, bool):
        return payload
    if isinstance(payload, (int, float)):
        return payload > 0
    if isinstance(payload, list):
        return len(payload) > 0
    if not isinstance(payload, dict):
        return None

    for key in _BOOL_KEYS:
        value = payload.get(key)
        if isinstance(value, bool):
            return value

    for key in _COUNT_KEYS:
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return value > 0

    for key in _LIST_KEYS:
        if key in payload:
            nested = _json_indicates_existing(payload[key])
            if nested is not None:
                return nested

    status_value = payload.get("status")
    if isinstance(status_value, str):
        lowered = status_value.lower()
        if lowered in {"found", "exists", "existing", "ok", "success"}:
            return True
        if lowered in {"not_found", "notfound", "missing", "none", "new"}:
            return False

    return None


def _build_external_url(
    *,
    base_url: str,
    path: str,
    cid: str,
    query_param: str,
) -> tuple[str, dict[str, str] | None]:
    base = base_url.strip().rstrip("/")
    normalized_path = path.strip()
    if not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"

    if "{cid}" in normalized_path:
        return base + normalized_path.replace("{cid}", cid), None

    query = urlencode({query_param: cid})
    return f"{base}{normalized_path}?{query}", None


def _auth_headers(api_key: str | None, header_name: str) -> dict[str, str]:
    if not api_key:
        return {}
    name = header_name.strip() or "X-API-Key"
    return {name: api_key}


def _request_error_detail(url: str, exc: httpx.RequestError) -> dict[str, str]:
    detail: dict[str, str] = {"error": str(exc), "url": url}
    lowered = url.lower()
    if "localhost" in lowered or "127.0.0.1" in lowered:
        detail["hint"] = (
            "case-service รันใน Docker แล้ว vsmart อยู่บนเครื่อง host — "
            "ตั้ง VSMART_MAIN_BASE_URL=http://host.docker.internal:8090 "
            "(ไม่ใช่ localhost)"
        )
    return detail


def _resolve_mso_logbook_url() -> str:
    if settings.mso_logbook_url.strip():
        return settings.mso_logbook_url.strip()
    base = settings.mso_logbook_base_url.strip().rstrip("/")
    if not base:
        return ""
    path = settings.mso_logbook_check_path.strip()
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def _interpret_mso_logbook_response(
    status_code: int,
    body: Any,
) -> tuple[bool, bool, str]:
    """คืน (found, available, message) ตามพฤติกรรม get-problem ของ MSO logbook."""
    if status_code == status.HTTP_404_NOT_FOUND:
        if isinstance(body, dict):
            detail = str(body.get("detail", ""))
            if "ไม่พบข้อมูลผู้ประสบปัญหา" in detail:
                return False, True, "not_found_problem"
        return False, False, "http_404"

    if status_code == status.HTTP_200_OK:
        return True, True, "found_problem"

    if status_code >= 400:
        return False, False, f"http_{status_code}"

    found = _json_indicates_existing(body)
    if found is not None:
        return found, True, "found" if found else "not_found"
    return False, False, "unrecognized_response"


async def _check_mso_logbook(cid: str, timeout: float) -> SourceCheckResult:
    """POST logbook get-problem — body ``{national_id: cid}``, header ``Api-Key``."""
    if not settings.check_case_enable_mso_logbook:
        return _disabled_source_result("mso_logbook")

    url = _resolve_mso_logbook_url()
    if not url:
        return SourceCheckResult(
            source="mso_logbook",
            found=False,
            available=False,
            message="not_configured",
        )

    field = settings.mso_logbook_body_field.strip() or "national_id"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        **_auth_headers(settings.mso_logbook_api_key, settings.mso_logbook_api_key_header),
    }
    payload = {field: cid}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException:
        logger.warning("check_case mso_logbook timeout cid=%s", cid)
        return SourceCheckResult(
            source="mso_logbook",
            found=False,
            available=False,
            message="timeout",
        )
    except httpx.RequestError as exc:
        logger.warning("check_case mso_logbook request_error cid=%s: %s", cid, exc)
        return SourceCheckResult(
            source="mso_logbook",
            found=False,
            available=False,
            message="request_error",
            detail=_request_error_detail(url, exc),
        )

    try:
        body: Any = response.json()
    except ValueError:
        body = None

    found, available, message = _interpret_mso_logbook_response(response.status_code, body)
    if not available and message == "unrecognized_response":
        return SourceCheckResult(
            source="mso_logbook",
            found=False,
            available=False,
            message=message,
            detail={"body": body if isinstance(body, dict) else {"raw": response.text[:500]}},
        )

    detail: dict[str, Any] | None = None
    if isinstance(body, (dict, list)):
        detail = {"body": body, "has_submission_audit": False}

    return SourceCheckResult(
        source="mso_logbook",
        found=found,
        available=available,
        message=message,
        detail=detail,
    )


async def _check_self_database(session: AsyncSession, cid: str) -> SourceCheckResult:
    if not settings.check_case_enable_vcare_self:
        return _disabled_source_result("vcare_main")

    person_id = await session.scalar(select(Person.id).where(Person.cid == cid))
    if person_id is None:
        return SourceCheckResult(
            source="vcare_main",
            found=False,
            available=True,
            message="no_person",
            detail={"applicant_count": 0},
        )

    applicant_count = await session.scalar(
        select(func.count()).select_from(Applicant).where(Applicant.persons_id == person_id)
    )
    count = int(applicant_count or 0)
    detail: dict[str, Any] = {"person_id": person_id, "applicant_count": count}
    if count > 0:
        vcare_prior = await fetch_vcare_prior_case_detail(session, person_id)
        if vcare_prior is not None:
            prior_case, audit_row = vcare_prior
            detail["prior_case"] = prior_case
            finalize_detail_submission_audit(
                detail,
                prior_case,
                source_label="VCARE",
                audit_row=audit_row,
            )
    return SourceCheckResult(
        source="vcare_main",
        found=count > 0,
        available=True,
        message="has_applicants" if count > 0 else "person_only",
        detail=detail,
    )


async def _check_external_source(
    *,
    source: CheckCaseSource,
    base_url: str,
    path: str,
    cid: str,
    query_param: str,
    api_key: str | None,
    api_key_header: str,
    timeout: float,
) -> SourceCheckResult:
    if not base_url.strip():
        return SourceCheckResult(
            source=source,
            found=False,
            available=False,
            message="not_configured",
        )

    url, _ = _build_external_url(
        base_url=base_url,
        path=path,
        cid=cid,
        query_param=query_param,
    )
    headers = _auth_headers(api_key, api_key_header)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
    except httpx.TimeoutException:
        logger.warning("check_case %s timeout cid=%s", source, cid)
        return SourceCheckResult(
            source=source,
            found=False,
            available=False,
            message="timeout",
        )
    except httpx.RequestError as exc:
        logger.warning("check_case %s request_error cid=%s: %s", source, cid, exc)
        return SourceCheckResult(
            source=source,
            found=False,
            available=False,
            message="request_error",
            detail=_request_error_detail(url, exc),
        )

    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        return SourceCheckResult(
            source=source,
            found=False,
            available=False,
            message="unauthorized",
            detail={
                "body": response.text[:500],
                "hint": "ตรวจ VSMART_MAIN_API_KEY ให้ตรงกับ volunteer_smart/.env",
            },
        )

    if response.status_code == status.HTTP_404_NOT_FOUND:
        return SourceCheckResult(
            source=source,
            found=False,
            available=True,
            message="not_found",
        )

    if response.status_code >= 400:
        return SourceCheckResult(
            source=source,
            found=False,
            available=False,
            message=f"http_{response.status_code}",
            detail={"body": response.text[:500]},
        )

    try:
        body: Any = response.json()
    except ValueError:
        return SourceCheckResult(
            source=source,
            found=False,
            available=False,
            message="invalid_json",
        )

    found = _json_indicates_existing(body)
    if found is None:
        return SourceCheckResult(
            source=source,
            found=False,
            available=False,
            message="unrecognized_response",
            detail={"body": body if isinstance(body, dict) else {"raw": body}},
        )

    prior = _parse_prior_case_from_payload(body) if isinstance(body, dict) else None
    detail = _merge_detail_with_prior(
        {"body": body, "has_submission_audit": prior is not None} if isinstance(body, dict) else None,
        prior,
    )
    if prior is not None and detail is not None:
        finalize_detail_submission_audit(detail, prior, source_label="Legacy")

    return SourceCheckResult(
        source=source,
        found=found,
        available=True,
        message="found" if found else "not_found",
        detail=detail,
    )


async def check_existing_case_by_cid(
    session: AsyncSession,
    cid: str,
) -> ExistingCaseCheckResult:
    """เช็ค CID กับแหล่งที่เปิดใช้งาน (vcare_main / MSO logbook / vsmart_main).

    ``is_existing_case`` เป็น OR ของ ``found`` จากทุกแหล่งที่ ``available=true``.
    """
    normalized = _normalize_cid(cid)
    timeout = settings.external_check_timeout_seconds

    # AsyncSession ไม่รองรับการใช้พร้อมกันใน gather — แยก query DB ออกจาก HTTP ภายนอก
    self_result = await _check_self_database(session, normalized)
    mso_result, vsmart_result = await asyncio.gather(
        _check_mso_logbook(normalized, timeout),
        _check_external_source(
            source="vsmart_main",
            base_url=settings.vsmart_main_base_url,
            path=settings.vsmart_main_check_path,
            cid=normalized,
            query_param=settings.vsmart_main_cid_query_param,
            api_key=settings.vsmart_main_api_key,
            api_key_header=settings.vsmart_main_api_key_header,
            timeout=timeout,
        ),
    )
    sources = [self_result, mso_result, vsmart_result]
    is_existing = any(s.found for s in sources if s.available)

    return ExistingCaseCheckResult(
        cid=normalized,
        is_existing_case=is_existing,
        sources=sources,
    )


@router.get("", response_model=ExistingCaseCheckResult)
async def get_existing_case_check(
    cid: str = Query(..., min_length=13, max_length=13, description="เลขบัตรประชาชน 13 หลัก"),
    session: AsyncSession = Depends(get_session),
    claims: CitizenClaims = Depends(require_citizen),
) -> ExistingCaseCheckResult:
    """Endpoint ทดสอบ / เรียกก่อนยื่นคำร้อง — ดูรายละเอียดได้ที่ module docstring."""
    assert_cid_owner(cid, claims)
    try:
        return await check_existing_case_by_cid(session, cid)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
