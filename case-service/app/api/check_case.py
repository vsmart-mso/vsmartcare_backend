"""ตรวจสอบรายใหม่ / รายเดิมจากเลขบัตรประชาชน (self DB, MSO logbook, vsmart_main).

เป้าหมาย
--------
ตอบว่า CID นี้เป็น **รายเดิม** (`is_existing_case=true`) หรือ **รายใหม่** (`false`)
โดยเช็ค 3 แหล่งพร้อมกัน แล้วรวมผล — ถ้าแหล่งใดแหล่งหนึ่งที่ตรวจได้พบข้อมูล ถือเป็นรายเดิม

แหล่งข้อมูล
-----------
- ``self``       — ฐาน case-service: มี ``applicants`` ของ ``persons`` ที่ cid ตรงกัน
- ``mso_logbook`` — API ภายนอก MSO logbook (ตั้ง ``MSO_LOGBOOK_*`` ใน .env)
- ``vsmart_main``   — API ภายนอก VSmart หลัก (ตั้ง ``VSMART_MAIN_*`` ใน .env)

การใช้งาน (HTTP)
----------------
::

    GET /v1/check-case?cid=1103701234561

    # ตัวอย่างคำตอบ
    # {
    #   "cid": "1103701234561",
    #   "is_existing_case": true,
    #   "sources": [
    #     {"source": "self", "found": false, "available": true, ...},
    #     {"source": "mso_logbook", "found": true, "available": true, ...},
    #     {"source": "vsmart_main", "found": false, "available": false,
    #      "message": "not_configured"}
    #   ]
    # }

การใช้งาน (เรียกจากโค้ด)
-------------------------
::

    from app.api.check_case import check_existing_case_by_cid

    result = await check_existing_case_by_cid(session, cid)
    if result.is_existing_case:
        ...  # รายเดิม

``POST /v1/cases`` เรียกฟังก์ชันนี้ก่อนบันทึก applicant แล้วตั้ง ``is_existing_case`` ให้อัตโนมัติ

ตั้งค่า .env (case-service)
---------------------------
::

    MSO_LOGBOOK_URL=https://volunteer-smart-beta.nu.ac.th/vapi/api-convert/logbook/get-problem/
    MSO_LOGBOOK_API_KEY=your-api-key
  # MSO_LOGBOOK_API_KEY_HEADER=Api-Key     # default
  # MSO_LOGBOOK_BODY_FIELD=national_id     # default
  # หรือแยก base + path แทน MSO_LOGBOOK_URL

    VSMART_MAIN_BASE_URL=https://vsmart.example.go.th
    VSMART_MAIN_CHECK_PATH=/api/v1/petition-forms/check-cid
    # หรือใส่ {cid} ใน path: /api/persons/{cid}/exists
    VSMART_MAIN_API_KEY=secret

    EXTERNAL_CHECK_TIMEOUT_SECONDS=10

ถ้าไม่ตั้ง ``*_BASE_URL`` แหล่งนั้นจะ ``available=false`` (ไม่นับใน ``is_existing_case``)

ความหมาย ``sources[]``
-----------------------
- ``found``     — พบข้อมูลในระบบนั้น (ใช้เมื่อ ``available=true``)
- ``available`` — ตรวจสอบสำเร็จ; ``false`` = ยังไม่ config / timeout / error / อ่าน response ไม่ได้
- ``message``   — สรุปสั้น ๆ เช่น ``not_found``, ``found``, ``not_configured``, ``timeout``
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

from ..core.database import get_session
from ..models.applicant import Applicant
from ..models.person import Person
from ..schemas.check_case import CheckCaseSource, ExistingCaseCheckResult, SourceCheckResult
from ..schemas.person import validate_thai_cid
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


def _normalize_cid(cid: str) -> str:
    return validate_thai_cid(cid.strip())


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

    return SourceCheckResult(
        source="mso_logbook",
        found=found,
        available=available,
        message=message,
        detail={"body": body} if isinstance(body, (dict, list)) else None,
    )


async def _check_self_database(session: AsyncSession, cid: str) -> SourceCheckResult:
    person_id = await session.scalar(select(Person.id).where(Person.cid == cid))
    if person_id is None:
        return SourceCheckResult(
            source="self",
            found=False,
            available=True,
            message="no_person",
            detail={"applicant_count": 0},
        )

    applicant_count = await session.scalar(
        select(func.count()).select_from(Applicant).where(Applicant.persons_id == person_id)
    )
    count = int(applicant_count or 0)
    return SourceCheckResult(
        source="self",
        found=count > 0,
        available=True,
        message="has_applicants" if count > 0 else "person_only",
        detail={"person_id": person_id, "applicant_count": count},
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

    return SourceCheckResult(
        source=source,
        found=found,
        available=True,
        message="found" if found else "not_found",
        detail={"body": body} if isinstance(body, dict) else None,
    )


async def check_existing_case_by_cid(
    session: AsyncSession,
    cid: str,
) -> ExistingCaseCheckResult:
    """เช็ค CID กับ self / MSO logbook / vsmart_main แบบขนาน.

    Args:
        session: AsyncSession ของ case-service
        cid: เลขบัตร 13 หลัก (ตัดช่องว่าง + ตรวจ checksum)

    Returns:
        ExistingCaseCheckResult — ``is_existing_case`` เป็น OR ของ ``found``
        จากทุกแหล่งที่ ``available=true``

    Raises:
        ValueError: cid ไม่ใช่ตัวเลข 13 หลัก หรือ checksum ผิด
    """
    normalized = _normalize_cid(cid)
    timeout = settings.external_check_timeout_seconds

    # AsyncSession ไม่รองรับการใช้พร้อมกันใน gather — แยก query DB ออกจาก HTTP ภายนอก
    self_result = await _check_self_database(session, normalized)
    (vsmart_result,) = await asyncio.gather(
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
    sources = [self_result, vsmart_result]
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
) -> ExistingCaseCheckResult:
    """Endpoint ทดสอบ / เรียกก่อนยื่นคำร้อง — ดูรายละเอียดได้ที่ module docstring."""
    try:
        return await check_existing_case_by_cid(session, cid)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
