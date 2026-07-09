from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Literal, Optional
from urllib.parse import urlencode
from uuid import UUID

import json

import httpx
from fastapi import APIRouter, Body, Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.openapi.utils import get_openapi
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from .case_for_staff_schema import (
    ArticleCreateBody,
    ArticleUpdateBody,
    CoverDocumentBatchCreateBody,
    CoverDocumentBatchUpdateBody,
    CaseForStaffApplicantStaffFieldsRead,
    CaseForStaffResponsibleDivisionRead,
    CaseForStaffResponsibleDivisionUpdateBody,
    StaffCaseSectionsUpdateBody,
    StaffDataEditLogBody,
    CaseForStaffFinanceListResponse,
    CaseForStaffFinanceRead as CaseForStaffFinanceListItem,
    CaseForStaffListResponse,
    CaseForStaffRead as CaseForStaffListItem,
    CaseForStaffStatusSummaryResponse,
)
from .services.staff_digest_dispatch import (
    StaffDigestDispatchResult,
    StaffDigestRequest,
    dispatch_staff_digest,
)
from .case_display_schema import CaseDisplayRead
from .dashboard_schema import (
    DashboardDistrictsRead,
    DashboardNationalOverviewRead,
    DashboardOverviewRead,
    DashboardProvincesRead,
    DashboardSubDistrictsRead,
)
from .submission_eligibility_schema import SubmissionEligibilityRead
from .middleware import CaptureAuthMiddleware, SecurityHeadersMiddleware, StaffRouteAuthMiddleware, merge_forward_headers
from .rate_limit import RateLimitMiddleware
from .settings import cors_origin_list, settings
from .vsmart_compat import case_compat_from_por_kor_1, staff_evidence_url, vsmart_internal_headers
from .welfare_case_schema import WelfareCaseCreate

_optional_bearer = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_bearer_any(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
) -> None:
    """Browser/data routes: Bearer JWT required (citizen, staff, or admin)."""
    if creds and creds.scheme.lower() == "bearer" and creds.credentials.strip():
        return
    raise HTTPException(status_code=401, detail="missing_bearer_token")


def require_bearer_or_trusted_api_key(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
    x_api_key: Optional[str] = Depends(_api_key_header),
) -> None:
    """Lookups/geo/dashboard: Bearer (frontend) or trusted X-API-Key (legacy VSMART)."""
    if creds and creds.scheme.lower() == "bearer" and creds.credentials.strip():
        return
    expected = (settings.bff_api_password or "").strip()
    if expected and (x_api_key or "").strip() == expected:
        return
    raise HTTPException(status_code=401, detail="missing_bearer_token")


def require_internal_api_key(
    x_api_key: Optional[str] = Depends(_api_key_header),
) -> None:
    """Trusted server clients only (volunteer_smart, cron)."""
    from .settings import is_production

    expected = (settings.bff_api_password or "").strip()
    if not expected:
        if is_production():
            raise HTTPException(status_code=503, detail="bff_api_password_not_configured")
        return
    if (x_api_key or "").strip() != expected:
        raise HTTPException(status_code=401, detail="invalid_api_key")


_require_bearer_any = [Depends(require_bearer_any)]
_require_bearer_or_trusted_api_key = [Depends(require_bearer_or_trusted_api_key)]
_require_internal_api_key = [Depends(require_internal_api_key)]


async def require_citizen_bearer(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
) -> str:
    """บังคับ Bearer token ของประชาชน — ใช้ forward ไป case-service (CR-01)."""
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    return f"Bearer {creds.credentials}"


@dataclass(frozen=True)
class CitizenOrVsmartAuth:
    mode: Literal["citizen", "vsmart"]
    authorization: str | None = None


async def require_citizen_or_vsmart_compat(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
    x_api_key: Optional[str] = Depends(_api_key_header),
) -> CitizenOrVsmartAuth:
    """Bearer citizen (เดิม) หรือ trusted X-API-Key เท่านั้น (VSMART legacy)."""
    if creds and creds.scheme.lower() == "bearer" and creds.credentials.strip():
        return CitizenOrVsmartAuth(mode="citizen", authorization=f"Bearer {creds.credentials}")
    expected = (settings.bff_api_password or "").strip()
    if expected and (x_api_key or "").strip() == expected:
        return CitizenOrVsmartAuth(mode="vsmart")
    raise HTTPException(status_code=401, detail="missing_bearer_token")


async def require_admin_bearer(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
) -> str:
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    return f"Bearer {creds.credentials}"


def _forward_auth_headers(authorization: Optional[str]) -> Dict[str, str]:
    """สร้าง header forward JWT ไป downstream (ว่าง = ไม่ส่ง)."""
    return {"Authorization": authorization} if authorization else {}


_TAGS = [
    {"name": "meta", "description": "ข้อมูล service และ health checks"},
    {"name": "applicants", "description": "การจัดการข้อมูล applicant"},
    {"name": "persons", "description": "reset / ลบข้อมูล persons และเคสที่ผูกกับบุคคล"},
    {"name": "cases", "description": "การบันทึกข้อมูล case"},
    {"name": "case_for_staff", "description": "รายการคำร้องสำหรับการใช้งานฝั่งเจ้าหน้าที่"},
    {
        "name": "eligibility",
        "description": "บันทึก screening_logs / welfare_request_consents (คัดกรองเบื้องต้น ความยินยอม) ผ่าน case-service",
    },
    {"name": "lookups", "description": "ข้อมูล master / lookup จาก case-service"},
    {"name": "geo", "description": "ข้อมูลจังหวัด อำเภอ ตำบล รหัสไปรษณีย์ จาก case-service"},
    {"name": "notifications", "description": "การแจ้งเตือน"},
    {"name": "auth", "description": "Login ThaiD"},
    {"name": "intake", "description": "ข้อมูลการรับเรื่อง (intake / payment / KTB) จาก case-service"},
    {"name": "satisfaction", "description": "ผลประเมินความพึงพอใจของผู้ยื่นคำขอ"},
    {"name": "admin", "description": "หลังบ้าน admin: login + เปิด/ปิดบริการรายจังหวัด + สร้างเคสสุ่ม"},
    {"name": "staff", "description": "Login เจ้าหน้าที่ + proxy case_for_staff/intake"},
    {"name": "ocr", "description": "OCR สมุดบัญชี (proxy → ocr-service)"},
    {"name": "dashboard", "description": "สรุปจำนวนคำร้องรายจังหวัด/อำเภอ สำหรับหน้า dashboard"},
]

_api_prefix = settings.bff_api_prefix

app = FastAPI(
    title=settings.service_name,
    version="0.1.0",
    openapi_tags=_TAGS,
    docs_url=f"{_api_prefix}/docs",
    redoc_url=f"{_api_prefix}/redoc",
    openapi_url=f"{_api_prefix}/openapi.json",
)

router = APIRouter()

app.add_middleware(CaptureAuthMiddleware)
app.add_middleware(StaffRouteAuthMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def custom_openapi() -> Dict[str, Any]:
    """สร้าง/แคช OpenAPI schema และเพิ่ม security scheme Bearer ให้ Swagger ใช้ปุ่ม Authorize."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    components = schema.setdefault("components", {}).setdefault("securitySchemes", {})
    components["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": (
            "access_token จาก ThaiD login (`POST /v1/auth/thaid/login` → callback) "
            f"หรือ staff/admin JWT — ใส่เฉพาะ token ไม่ต้องพิมพ์คำว่า Bearer"
        ),
    }
    components["BffApiKey"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "รหัส trusted server clients เท่านั้น (volunteer_smart) — ไม่ใช้จาก browser",
    }
    schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]



@router.get("/", tags=["meta"], summary="สถานะ service")
def root():
    """ตอบชื่อบริการและสถานะ OK สำหรับเช็กว่า BFF ทำงานอยู่."""
    return {"service": settings.service_name, "ok": True}


@router.get("/healthz", tags=["meta"], summary="Liveness probe")
def healthz():
    """Probe ว่า process ยังมีชีวิต (ไม่ต้องพึ่ง backend อื่น) — ใช้กับ orchestrator/k8s liveness."""
    return {"ok": True}


@router.get("/readyz", tags=["meta"], summary="Readiness probe")
def readyz():
    """Probe ความพร้อมรับ traffic — ขยายให้เช็ก downstream ได้ถ้าต้องการ."""
    return {"ok": True}


def _http_error_detail_from_response(r: httpx.Response) -> Any:
    """ดึง detail จาก body JSON ของ downstream — ลดกรณี detail เป็น string JSON ซ้อน."""
    detail: Any = r.text
    ct = (r.headers.get("content-type") or "").lower()
    if "application/json" not in ct:
        return detail
    try:
        body = r.json()
    except ValueError:
        return detail
    if not isinstance(body, dict):
        return body
    d = body.get("detail", body)
    if isinstance(d, str) and d.strip().startswith("{"):
        try:
            inner = json.loads(d)
            if isinstance(inner, dict) and "detail" in inner:
                return inner["detail"]
        except json.JSONDecodeError:
            pass
    return d


def _json_safe_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """แปลง date/datetime/Decimal ใน dict ให้ httpx json= serialize ได้."""

    def _default(value: object) -> str:
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return format(value, "f")
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

    return json.loads(json.dumps(payload, default=_default))


async def _post(
    url: str,
    json: Dict[str, Any],
    *,
    timeout: float = 30.0,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """ยิง HTTP POST JSON; ถ้า status >= 400 จะยก HTTPException."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=_json_safe_payload(json), headers=merge_forward_headers(headers))
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=_http_error_detail_from_response(r))
        return r.json()


async def _post_evidence_multipart(
    url: str,
    form_fields: Dict[str, Any],
    file: UploadFile,
    *,
    timeout: float = 120.0,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """ส่ง multipart ไป case-service สำหรับหลักฐานรูป (ไฟล์จริง ไม่ใช่ Base64)."""
    content = await file.read()
    data: Dict[str, str] = {}
    for k, v in form_fields.items():
        if v is None:
            continue
        data[str(k)] = str(v)

    fname = file.filename or "upload"
    ct = file.content_type or "application/octet-stream"
    async with httpx.AsyncClient(timeout=timeout) as client:
        files = {"file": (fname, content, ct)}
        r = await client.post(url, data=data, files=files, headers=merge_forward_headers(headers))
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


async def _put_evidence_multipart(
    url: str,
    form_fields: Dict[str, Any],
    file: UploadFile,
    *,
    timeout: float = 120.0,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """ส่ง multipart PUT ไป case-service สำหรับแก้ไขรูปหลักฐาน."""
    content = await file.read()
    data: Dict[str, str] = {}
    for k, v in form_fields.items():
        if v is None:
            continue
        data[str(k)] = str(v)

    fname = file.filename or "upload"
    ct = file.content_type or "application/octet-stream"
    async with httpx.AsyncClient(timeout=timeout) as client:
        files = {"file": (fname, content, ct)}
        r = await client.put(url, data=data, files=files, headers=merge_forward_headers(headers))
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


async def _patch(
    url: str,
    json: Dict[str, Any],
    *,
    timeout: float = 30.0,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """ยิง HTTP PATCH JSON; ถ้า status >= 400 จะยก HTTPException."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.patch(url, json=_json_safe_payload(json), headers=merge_forward_headers(headers))
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=_http_error_detail_from_response(r))
        return r.json()


async def _put(
    url: str,
    json: Dict[str, Any],
    *,
    timeout: float = 30.0,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """ยิง HTTP PUT JSON; ถ้า status >= 400 จะยก HTTPException."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.put(url, json=_json_safe_payload(json), headers=merge_forward_headers(headers))
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=_http_error_detail_from_response(r))
        return r.json()


async def _get(url: str, headers: Optional[Dict[str, str]] = None) -> Any:
    """ยิง HTTP GET พร้อม header ได้เลือก คืน JSON (object หรือ array); ถ้า status >= 400 จะยก HTTPException."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, headers=merge_forward_headers(headers))
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=_http_error_detail_from_response(r))
        return r.json()


async def _get_raw(
    url: str,
    *,
    timeout: float = 60.0,
    headers: Optional[Dict[str, str]] = None,
) -> httpx.Response:
    """GET แบบคืน Response ดิบ (ใช้โหลดไฟล์ไบนารี)."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(url, headers=merge_forward_headers(headers))
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=_http_error_detail_from_response(r))
        return r


async def _delete(
    url: str,
    *,
    timeout: float = 30.0,
    headers: Optional[Dict[str, str]] = None,
) -> Any:
    """ยิง HTTP DELETE; คืน JSON ถ้ามี body และถ้า status >= 400 จะยก HTTPException."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.delete(url, headers=merge_forward_headers(headers))
        if r.status_code >= 400:
            detail: Any = r.text
            ct = (r.headers.get("content-type") or "").lower()
            try:
                if "application/json" in ct:
                    detail = r.json()
            except ValueError:
                pass
            raise HTTPException(status_code=r.status_code, detail=detail)

        if not r.content:
            return None

        try:
            return r.json()
        except ValueError:
            return {"raw": r.text}


async def _post_thaid_auth_login(json_body: Dict[str, Any]) -> Dict[str, Any]:
    """POST ไป thaid-auth-service พร้อมเช็ก URL, เครือข่าย, timeout และ JSON."""
    base = settings.thaid_auth_service_url.strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=500,
            detail="thaid_auth_service_url_not_configured",
        )
    url = f"{base}/v1/auth/thaid/login"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=json_body)
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail={"error": "thaid_auth_timeout", "message": str(exc)},
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "thaid_auth_unreachable",
                "message": str(exc),
                "url": url,
                "hint": "รัน thaid-auth-service ให้ฟังที่ base URL นี้ หรือตั้ง THAID_AUTH_SERVICE_URL ใน .env ของ BFF ให้ตรงพอร์ตจริง (Docker: ใช้ host.docker.internal แทน localhost ถ้า service รันบนเครื่อง host)",
            },
        ) from exc

    if r.status_code >= 400:
        detail: Any = r.text
        ct = (r.headers.get("content-type") or "").lower()
        try:
            if "application/json" in ct:
                detail = r.json()
        except ValueError:
            pass
        raise HTTPException(status_code=r.status_code, detail=detail)

    try:
        return r.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "thaid_auth_invalid_json", "message": str(exc)},
        ) from exc


class ScreeningLogCreateRequest(BaseModel):
    """Body สำหรับ `POST /v1/screening-logs` — ตรงกับ case-service ScreeningLogCreate."""

    person_id: int
    criteria_version: Optional[str] = Field(None, max_length=255)
    failure_reason_code: Optional[str] = Field(None, max_length=255)
    screening_status: bool = False
    input_data_snapshot: Optional[Dict[str, Any]] = None
    # สถานะความเดือดร้อนที่ผู้ใช้เลือก (เลือกได้หลายข้อ) — list ของ id จาก hardship_status_types
    hardship_status_ids: Optional[list[int]] = None
    ip_address: Optional[str] = Field(None, max_length=255)
    user_agent: Optional[str] = Field(None, max_length=500)


class ScreeningLogReadResponse(BaseModel):
    """ผลลัพธ์หลังบันทึก screening_logs — ตรงกับ case-service ScreeningLogRead."""

    id: int
    person_id: int
    criteria_version: Optional[str] = None
    failure_reason_code: Optional[str] = None
    screening_status: bool
    input_data_snapshot: Optional[Dict[str, Any]] = None
    hardship_status_ids: Optional[list[int]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class WelfareRequestConsentCreateRequest(BaseModel):
    """Body สำหรับ `POST /v1/welfare-request-consents` — ตรงกับ case-service WelfareRequestConsentCreate."""

    person_id: int
    consent_type: Optional[str] = Field(None, max_length=100)
    initial_pdpa_accepted: bool = False
    initial_terms_accepted: bool = False
    initial_warning_accepted: bool = False
    final_data_correct_accepted: bool = False


class WelfareRequestConsentReadResponse(BaseModel):
    """ผลลัพธ์หลังบันทึก welfare_request_consents — ตรงกับ case-service WelfareRequestConsentRead."""

    id: int
    person_id: int
    consent_type: Optional[str] = None
    initial_pdpa_accepted: bool
    initial_terms_accepted: bool
    initial_warning_accepted: bool
    final_data_correct_accepted: bool
    created_at: datetime
    updated_at: datetime


class ApplicantDeleteByCidResponse(BaseModel):
    cid: str = Field(..., min_length=13, max_length=13)
    person_id: int
    deleted_applicant_ids: list[int] = Field(default_factory=list)
    deleted_count: int = Field(..., ge=0)
    deleted_screening_log_ids: list[int] = Field(default_factory=list)
    deleted_screening_log_count: int = Field(..., ge=0)
    deleted_welfare_request_consent_ids: list[int] = Field(default_factory=list)
    deleted_welfare_request_consent_count: int = Field(..., ge=0)


class PersonDeleteByCidResponse(BaseModel):
    cid: str = Field(..., min_length=13, max_length=13)
    person_id: int
    person_deleted: bool = True
    deleted_applicant_ids: list[int] = Field(default_factory=list)
    deleted_count: int = Field(..., ge=0)
    deleted_screening_log_ids: list[int] = Field(default_factory=list)
    deleted_screening_log_count: int = Field(..., ge=0)
    deleted_welfare_request_consent_ids: list[int] = Field(default_factory=list)
    deleted_welfare_request_consent_count: int = Field(..., ge=0)
    cleared_case_payment_refs: int = Field(0, ge=0)


class PersonDeleteAllResponse(BaseModel):
    deleted_person_count: int = Field(..., ge=0)
    deleted_person_ids: list[int] = Field(default_factory=list)
    deleted_applicant_count: int = Field(..., ge=0)
    deleted_applicant_ids: list[int] = Field(default_factory=list)
    deleted_screening_log_count: int = Field(..., ge=0)
    deleted_welfare_request_consent_count: int = Field(..., ge=0)
    cleared_case_payment_refs: int = Field(0, ge=0)


class CaseForStaffWelfareRequestStatusBody(BaseModel):
    applicant_id: int = Field(..., ge=1)
    current_status_id: int = Field(..., ge=1)
    remarks: Optional[str] = None
    update_by_sdshv: Optional[str] = Field(None, max_length=255)


class CaseForStaffApplicantStaffFieldsUpdateBody(BaseModel):
    type_money_category_id: Optional[int] = Field(
        None,
        ge=1,
        description="ประเภทเงินช่วยเหลือ — ส่ง null เพื่อล้างค่า",
    )
    sw_explorer_sdshv: Optional[str] = Field(
        None,
        max_length=255,
        description="รหัส/ชื่อผู้สำรวจ SDSHV — ส่ง null เพื่อล้างค่า",
    )


class ApproveCaseCreateBody(BaseModel):
    applicant_id: int = Field(..., ge=1)
    approve_status: bool = False
    esignature: Optional[str] = None
    user_sdshv: Optional[str] = Field(None, max_length=255)
    reject_reason: Optional[str] = Field(
        None,
        min_length=1,
        description="เหตุผลที่ พมจ. ไม่อนุมัติ ส่งต่อไป case-service เมื่อ approve_status=false",
    )


class WelfareDdaRefDetailCreateBody(BaseModel):
    applicant_id: int = Field(..., ge=1)


class WelfareDdaRefBundleCreateBody(BaseModel):
    dda_ref: str = Field(..., min_length=1, max_length=255)
    dda_ref_detail: list[WelfareDdaRefDetailCreateBody] = Field(..., min_length=1)
    user_sdshv: Optional[str] = Field(None, max_length=255)


class WelfarePaymentUpdateBody(BaseModel):
    is_037_or_038: Optional[bool] = None
    payment_number: Optional[str] = Field(None, max_length=255)
    payment_038_reason: Optional[str] = Field(None, max_length=255)
    transaction_date: Optional[date] = None
    effective_date: Optional[date] = None
    user_sdshv: Optional[str] = Field(None, max_length=255)
    upload_batch_id: Optional[UUID] = Field(
        None,
        description="UUID ร่วมกันต่อการบันทึกครั้งเดียวใน modal (037+038)",
    )


class WelfarePaymentPartialBody(BaseModel):
    payment_number: Optional[str] = Field(None, max_length=255)
    payment_038_reason: Optional[str] = Field(None, max_length=255)
    transaction_date: Optional[date] = None
    effective_date: Optional[date] = None


class WelfarePaymentBatchUpdateBody(BaseModel):
    upload_batch_id: UUID
    user_sdshv: Optional[str] = Field(None, max_length=255)
    payment_037: WelfarePaymentPartialBody
    payment_038: WelfarePaymentPartialBody


class WelfareReviewCommentCreateBody(BaseModel):
    review_field_id: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1)


class WelfareEditRequestCreateBody(BaseModel):
    applicant_id: int = Field(..., ge=1)
    update_by_sdshv: Optional[str] = Field(None, max_length=255)
    remarks: Optional[str] = None
    comments: list[WelfareReviewCommentCreateBody] = Field(..., min_length=1)


class MsoForwardCreateBody(BaseModel):
    send_channel: Literal["ministry", "logbook"] = Field(
        ...,
        description="`ministry` = ส่งต่อเข้าหระทรวง, `logbook` = ส่งต่อ MSO logbook",
    )
    send_by_sdshv: Optional[str] = Field(None, max_length=255)
    json_case: Optional[dict[str, Any]] = None
    response_code: Optional[str] = Field(None, max_length=255)
    response_text: Optional[str] = None


class MoreMsoUpsertBody(BaseModel):
    follow_date: Optional[str] = Field(None, max_length=255)
    help_number: Optional[str] = Field(None, max_length=255)
    help_date: Optional[date] = None
    approve_name: Optional[str] = Field(None, max_length=255)
    approve_number: Optional[str] = Field(None, max_length=255)
    approve_date: Optional[date] = None
    receive_date: Optional[date] = None
    cashier: Optional[str] = Field(None, max_length=255)
    cashier_name: Optional[str] = Field(None, max_length=255)
    follower_name: Optional[str] = Field(None, max_length=255)
    follower_position_vsmart_id: Optional[str] = Field(None, max_length=255)
    follower_department_vsmart_id: Optional[str] = Field(None, max_length=255)
    follower_tel: Optional[str] = Field(None, max_length=255)
    follower_date: Optional[date] = None
    follower_result: Optional[str] = None
    follower_method: Optional[int] = None
    follower_type: Optional[int] = None


def _case_for_staff_finance_query_pairs(
    *,
    province_id: int,
    case_number: Optional[str],
    current_status: Optional[str],
    current_status_id: Optional[list[int]],
    firstname: Optional[str],
    lastname: Optional[str],
    cid: Optional[str],
    datetime_create: Optional[date],
    province_name: Optional[str],
    district_id: Optional[int],
    district_name: Optional[str],
    subdistrict_id: Optional[int],
    subdistrict_name: Optional[str],
    subdistrict_postcode_id: Optional[int],
    postcode: Optional[str],
    type_money_id: Optional[list[int]],
) -> list[tuple[str, Any]]:
    pairs: list[tuple[str, Any]] = [("province_id", province_id)]
    if case_number is not None:
        pairs.append(("case_number", case_number))
    if current_status is not None:
        pairs.append(("current_status", current_status))
    if current_status_id:
        for cs in current_status_id:
            pairs.append(("current_status_id", cs))
    if firstname is not None:
        pairs.append(("firstname", firstname))
    if lastname is not None:
        pairs.append(("lastname", lastname))
    if cid is not None:
        pairs.append(("cid", cid))
    if datetime_create is not None:
        pairs.append(("datetime_create", datetime_create.isoformat()))
    if province_name is not None:
        pairs.append(("province_name", province_name))
    if district_id is not None:
        pairs.append(("district_id", district_id))
    if district_name is not None:
        pairs.append(("district_name", district_name))
    if subdistrict_id is not None:
        pairs.append(("subdistrict_id", subdistrict_id))
    if subdistrict_name is not None:
        pairs.append(("subdistrict_name", subdistrict_name))
    if subdistrict_postcode_id is not None:
        pairs.append(("subdistrict_postcode_id", subdistrict_postcode_id))
    if postcode is not None:
        pairs.append(("postcode", postcode))
    if type_money_id:
        for tm in type_money_id:
            pairs.append(("type_money_id", tm))
    return pairs


@router.post(
    "/v1/cases",
    tags=["cases"],
    summary="สร้างคำร้อง (บันทึก applicants และตารางย่อย)",
    description=(
        "ส่งต่อ `POST …/v1/cases` ใน case-service — บันทึก applicant, address, "
        "dependency_loads, economic_infos, welfare_request_types, welfare_histories, "
        "welfare_request_status จาก body"
    ),
)
async def create_case(
    body: WelfareCaseCreate,
    authorization: str = Depends(require_citizen_bearer),
) -> Dict[str, Any]:
    """รับ JSON ครบแล้วส่งต่อไปบันทึกฐานข้อมูล (ยังไม่รวมรูปหลักฐาน — ใช้ `/v1/cases/{applicant_id}/evidences`)."""
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(mode="json")
    return await _post(
        f"{base}/v1/cases",
        json=payload,
        timeout=120.0,
        headers=_forward_auth_headers(authorization),
    )


@router.post(
    "/v1/cases/{applicant_id}/evidences",
    tags=["cases"],
    summary="อัปโหลดรูปหลักฐาน (multipart)",
    description="ส่งต่อ `POST …/v1/cases/{applicant_id}/evidences` — เก็บไฟล์รูปลงจานและ welfare_evidences",
)
async def upload_case_evidence(
    applicant_id: int,
    attachment_type_id: int = Form(...),
    file_other_type_name: Optional[str] = Form(None),
    # household_member_seq: ส่งมาเมื่ออัปโหลดรูปของสมาชิกในครัวเรือน
    # BFF ต้องรับและส่งต่อ — case-service จะ resolve เป็น household_member_id เอง
    household_member_seq: Optional[int] = Form(None, ge=1),
    file: UploadFile = File(...),
    auth: CitizenOrVsmartAuth = Depends(require_citizen_or_vsmart_compat),
) -> Dict[str, Any]:
    base = settings.case_service_url.rstrip("/")
    if auth.mode == "vsmart":
        url = staff_evidence_url(base, applicant_id)
        headers = vsmart_internal_headers()
    else:
        url = f"{base}/v1/cases/{applicant_id}/evidences"
        headers = _forward_auth_headers(auth.authorization)
    return await _post_evidence_multipart(
        url,
        {
            "attachment_type_id": attachment_type_id,
            "file_other_type_name": file_other_type_name,
            "household_member_seq": household_member_seq,
        },
        file,
        headers=headers,
    )


@router.get(
    "/v1/cases/display",
    tags=["cases"],
    summary="ดึงรายการสรุปคำร้องตาม persons_id",
    description=(
        "ส่งต่อ `GET …/v1/cases/display?persons_id=…` — คืน list ของ applicant_id, case_number, "
        "datetime_create, time_count_process, is_existing_case, current_status, description_public"
    ),
    response_model=list[CaseDisplayRead],
)
async def list_cases_display(
    persons_id: int,
    authorization: str = Depends(require_citizen_bearer),
) -> list[CaseDisplayRead]:
    base = settings.case_service_url.rstrip("/")
    data = await _get(
        f"{base}/v1/cases/display?persons_id={persons_id}",
        headers=_forward_auth_headers(authorization),
    )
    return [CaseDisplayRead.model_validate(item) for item in data]


@router.get(
    "/v1/cases/submission-eligibility",
    tags=["cases"],
    summary="ตรวจสอบสิทธิ์ยื่นคำขอและเข้าพอร์ทัลประชาชน",
    description=(
        "ส่งต่อ `GET …/v1/cases/submission-eligibility?persons_id=…` — "
        "คืน can_submit, can_access_portal, reason และวันที่ยื่นได้ครั้งถัดไป"
    ),
    response_model=SubmissionEligibilityRead,
)
async def get_submission_eligibility(
    persons_id: int,
    authorization: str = Depends(require_citizen_bearer),
) -> SubmissionEligibilityRead:
    base = settings.case_service_url.rstrip("/")
    data = await _get(
        f"{base}/v1/cases/submission-eligibility?persons_id={persons_id}",
        headers=_forward_auth_headers(authorization),
    )
    return SubmissionEligibilityRead.model_validate(data)


@router.get(
    "/v1/case_for_staff",
    tags=["case_for_staff"],
    summary="ดึงรายการคำร้องสำหรับเจ้าหน้าที่",
    description=(
        "ส่งต่อ `GET …/v1/case_for_staff` ใน case-service โดยบังคับ `province_id` "
        "และรองรับ filter เพิ่มเติมจาก case_number, current_status, firstname, lastname, cid, "
        "datetime_create, district/subdistrict/postcode, type_money_id (type_money_category) พร้อมคืน is_emergency, "
        "is_existing_case, time_count_process, count_037, count_038, is_037_or_038, have_dda_ref (สรุป welfare_payment เหมือน /finance)"
    ),
    response_model=CaseForStaffListResponse,
)
async def list_cases_for_staff(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการค้นหา"),
    case_number: Optional[str] = Query(None, description="ค้นหาจากเลข case"),
    current_status: Optional[str] = Query(None, description="ค้นหาจากข้อความสถานะฝั่งเจ้าหน้าที่"),
    firstname: Optional[str] = Query(None, description="ค้นหาจากชื่อ"),
    lastname: Optional[str] = Query(None, description="ค้นหาจากนามสกุล"),
    cid: Optional[str] = Query(None, description="ค้นหาจากเลขบัตรประชาชน"),
    datetime_create: Optional[date] = Query(None, description="วันที่สร้าง case (YYYY-MM-DD)"),
    province_name: Optional[str] = Query(None, description="ค้นหาจากชื่อจังหวัด"),
    district_id: Optional[int] = Query(None, description="กรองตามอำเภอ"),
    district_name: Optional[str] = Query(None, description="ค้นหาจากชื่ออำเภอ"),
    subdistrict_id: Optional[int] = Query(None, description="กรองตามตำบล"),
    subdistrict_name: Optional[str] = Query(None, description="ค้นหาจากชื่อตำบล"),
    subdistrict_postcode_id: Optional[int] = Query(None, description="กรองตามแถว bridge sub_districts_postcode"),
    postcode: Optional[str] = Query(None, description="ค้นหาจากรหัสไปรษณีย์"),
    type_money_id: Optional[int] = Query(None, description="กรองตาม type_money_category.id"),
) -> CaseForStaffListResponse:
    base = settings.case_service_url.rstrip("/")
    params = {
        "province_id": province_id,
        "case_number": case_number,
        "current_status": current_status,
        "firstname": firstname,
        "lastname": lastname,
        "cid": cid,
        "datetime_create": datetime_create.isoformat() if datetime_create is not None else None,
        "province_name": province_name,
        "district_id": district_id,
        "district_name": district_name,
        "subdistrict_id": subdistrict_id,
        "subdistrict_name": subdistrict_name,
        "subdistrict_postcode_id": subdistrict_postcode_id,
        "postcode": postcode,
        "type_money_id": type_money_id,
    }
    query_string = urlencode({k: v for k, v in params.items() if v is not None})
    data = await _get(f"{base}/v1/case_for_staff?{query_string}")
    return CaseForStaffListResponse.model_validate(
        {
            **data,
            "items": [CaseForStaffListItem.model_validate(item) for item in data.get("items", [])],
        }
    )


@router.get(
    "/v1/case_for_staff/finance",
    tags=["case_for_staff"],
    summary="รายการคำร้องสำหรับตารางการเงิน",
    description=(
        "ส่งต่อ `GET …/v1/case_for_staff/finance` — บังคับ `province_id`, เฉพาะเคสที่ approve_case.approve_status = true, "
        "รองรับกรอง type_money_id / current_status_id หลายค่า, คืน is_approved, dda_ref, have_dda_ref, count_037, count_038, "
        "is_037_or_038, bank_name_id, bank_code, bank_account_no, email_address, mobile_phone, money_amount"
    ),
    response_model=CaseForStaffFinanceListResponse,
)
async def list_cases_for_staff_finance(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการค้นหา"),
    case_number: Optional[str] = Query(None, description="ค้นหาจากเลข case"),
    current_status: Optional[str] = Query(None, description="ค้นหาจากข้อความสถานะฝั่งเจ้าหน้าที่"),
    current_status_id: Optional[list[int]] = Query(
        None,
        description="กรองตาม current_status_id ได้หลายค่า",
    ),
    firstname: Optional[str] = Query(None, description="ค้นหาจากชื่อ"),
    lastname: Optional[str] = Query(None, description="ค้นหาจากนามสกุล"),
    cid: Optional[str] = Query(None, description="ค้นหาจากเลขบัตรประชาชน"),
    datetime_create: Optional[date] = Query(None, description="วันที่สร้าง case (YYYY-MM-DD)"),
    province_name: Optional[str] = Query(None, description="ค้นหาจากชื่อจังหวัด"),
    district_id: Optional[int] = Query(None, description="กรองตามอำเภอ"),
    district_name: Optional[str] = Query(None, description="ค้นหาจากชื่ออำเภอ"),
    subdistrict_id: Optional[int] = Query(None, description="กรองตามตำบล"),
    subdistrict_name: Optional[str] = Query(None, description="ค้นหาจากชื่อตำบล"),
    subdistrict_postcode_id: Optional[int] = Query(None, description="กรองตามแถว bridge sub_districts_postcode"),
    postcode: Optional[str] = Query(None, description="ค้นหาจากรหัสไปรษณีย์"),
    type_money_id: Optional[list[int]] = Query(
        None,
        description="กรองตาม type_money_category.id ได้หลายค่า",
    ),
) -> CaseForStaffFinanceListResponse:
    base = settings.case_service_url.rstrip("/")
    pairs = _case_for_staff_finance_query_pairs(
        province_id=province_id,
        case_number=case_number,
        current_status=current_status,
        current_status_id=current_status_id,
        firstname=firstname,
        lastname=lastname,
        cid=cid,
        datetime_create=datetime_create,
        province_name=province_name,
        district_id=district_id,
        district_name=district_name,
        subdistrict_id=subdistrict_id,
        subdistrict_name=subdistrict_name,
        subdistrict_postcode_id=subdistrict_postcode_id,
        postcode=postcode,
        type_money_id=type_money_id,
    )
    query_string = urlencode(pairs)
    data = await _get(f"{base}/v1/case_for_staff/finance?{query_string}")
    return CaseForStaffFinanceListResponse.model_validate(
        {
            **data,
            "items": [CaseForStaffFinanceListItem.model_validate(item) for item in data.get("items", [])],
        }
    )


@router.get(
    "/v1/case_for_staff/finance/with-dda-ref",
    tags=["case_for_staff"],
    summary="รายการคำร้องการเงิน (มี welfare_payment + welfare_dda_ref)",
    description=(
        "ส่งต่อ `GET …/v1/case_for_staff/finance/with-dda-ref` — เหมือน /finance แต่ดึงเฉพาะ applicant "
        "ที่มีแถวใน welfare_payment ผูกกับ welfare_dda_ref แล้ว; "
        "ไม่รวมเคสที่ current_status_id >= 10 (อยู่ระหว่างการเบิกขึ้นไป); "
        "คืน is_approved และฟิลด์ธนาคาร/ติดต่อเหมือน /finance"
    ),
    response_model=CaseForStaffFinanceListResponse,
)
async def list_cases_for_staff_finance_with_dda_ref(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการค้นหา"),
    case_number: Optional[str] = Query(None),
    current_status: Optional[str] = Query(None),
    current_status_id: Optional[list[int]] = Query(None),
    firstname: Optional[str] = Query(None),
    lastname: Optional[str] = Query(None),
    cid: Optional[str] = Query(None),
    datetime_create: Optional[date] = Query(None),
    province_name: Optional[str] = Query(None),
    district_id: Optional[int] = Query(None),
    district_name: Optional[str] = Query(None),
    subdistrict_id: Optional[int] = Query(None),
    subdistrict_name: Optional[str] = Query(None),
    subdistrict_postcode_id: Optional[int] = Query(None),
    postcode: Optional[str] = Query(None),
    type_money_id: Optional[list[int]] = Query(None),
) -> CaseForStaffFinanceListResponse:
    base = settings.case_service_url.rstrip("/")
    pairs = _case_for_staff_finance_query_pairs(
        province_id=province_id,
        case_number=case_number,
        current_status=current_status,
        current_status_id=current_status_id,
        firstname=firstname,
        lastname=lastname,
        cid=cid,
        datetime_create=datetime_create,
        province_name=province_name,
        district_id=district_id,
        district_name=district_name,
        subdistrict_id=subdistrict_id,
        subdistrict_name=subdistrict_name,
        subdistrict_postcode_id=subdistrict_postcode_id,
        postcode=postcode,
        type_money_id=type_money_id,
    )
    query_string = urlencode(pairs)
    data = await _get(f"{base}/v1/case_for_staff/finance/with-dda-ref?{query_string}")
    return CaseForStaffFinanceListResponse.model_validate(
        {
            **data,
            "items": [CaseForStaffFinanceListItem.model_validate(item) for item in data.get("items", [])],
        }
    )


@router.patch(
    "/v1/case_for_staff/welfare-payment",
    tags=["case_for_staff"],
    summary="อัปเดต welfare_payment ตาม applicant_id",
    description=(
        "ส่งต่อ `PATCH …/v1/case_for_staff/welfare-payment?applicant_id=…` — 038 ครั้งแรก PATCH แถว null, "
        "038 ครั้งถัดไป INSERT แถวใหม่; 037 ครั้งเดียวต่อรอบ DDA; คืน id สำหรับอัปโหลด PDF; "
        "037-only → current_status_id=10; 037+038 ในรอบเดียวกัน → current_status_id=3"
    ),
)
async def update_welfare_payment_for_staff(
    applicant_id: int = Query(..., ge=1),
    body: WelfarePaymentUpdateBody = Body(...),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_unset=True, mode="json")
    return await _patch(
        f"{base}/v1/case_for_staff/welfare-payment?applicant_id={applicant_id}",
        json=payload,
    )


@router.patch(
    "/v1/case_for_staff/welfare-payment/batch",
    tags=["case_for_staff"],
    summary="บันทึก welfare_payment 037+038 ในครั้งเดียว",
    description=(
        "ส่งต่อ `PATCH …/v1/case_for_staff/welfare-payment/batch?applicant_id=…` — "
        "บันทึก 037 และ 038 ใน transaction เดียวด้วย upload_batch_id ร่วมกัน; "
        "สถานะคำร้องเป็น current_status_id=3 (อยู่ระหว่างการเบิก)"
    ),
)
async def update_welfare_payment_batch_for_staff(
    applicant_id: int = Query(..., ge=1),
    body: WelfarePaymentBatchUpdateBody = Body(...),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_unset=True, mode="json")
    return await _patch(
        f"{base}/v1/case_for_staff/welfare-payment/batch?applicant_id={applicant_id}",
        json=payload,
    )


@router.patch(
    "/v1/case_for_staff/welfare-payment/{welfare_payment_id}",
    tags=["case_for_staff"],
    summary="อัปเดต welfare_payment ตาม id (แก้ไขรอบเดิม)",
    description=(
        "ส่งต่อ `PATCH …/welfare-payment/{welfare_payment_id}?applicant_id=…` — "
        "แก้ไขแถวที่ระบุโดยตรง ไม่สร้างแถว 038 ใหม่"
    ),
)
async def update_welfare_payment_by_id_for_staff(
    welfare_payment_id: int,
    applicant_id: int = Query(..., ge=1),
    body: WelfarePaymentUpdateBody = Body(...),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_unset=True, mode="json")
    return await _patch(
        f"{base}/v1/case_for_staff/welfare-payment/{welfare_payment_id}"
        f"?applicant_id={applicant_id}",
        json=payload,
    )


@router.post(
    "/v1/case_for_staff/applicant/{applicant_id}/file-payment",
    tags=["case_for_staff"],
    summary="อัปโหลด PDF file_payment",
    description=(
        "ส่งต่อ multipart ไป case-service — ฟิลด์ form: attachment_type_id (9=PDF 037, 10=PDF 038), "
        "welfare_payment_id (แนะนำหลัง PATCH 038), file_payment_id (แก้ไข — อัปเดตแถวเดิม), "
        "upload_batch_id (modal เดียว), file (PDF); "
        "ไม่ส่ง welfare_payment_id จะใช้แถวล่าสุดบน DDA ปัจจุบัน"
    ),
    status_code=status.HTTP_201_CREATED,
)
async def upload_file_payment_for_staff(
    applicant_id: int,
    attachment_type_id: int = Form(..., ge=1),
    welfare_payment_id: Optional[int] = Form(
        None,
        ge=1,
        description="id จาก welfare_payment หลัง PATCH — ไม่ส่งจะใช้แถวล่าสุดบน DDA ปัจจุบัน",
    ),
    file_payment_id: Optional[int] = Form(
        None,
        ge=1,
        description="แก้ไขประวัติ — อัปเดตแถว file_payment เดิม",
    ),
    upload_batch_id: Optional[UUID] = Form(
        None,
        description="UUID ร่วมกันต่อการบันทึกครั้งเดียวใน modal",
    ),
    file: UploadFile = File(..., description="ไฟล์ PDF"),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    url = f"{base}/v1/case_for_staff/applicant/{applicant_id}/file-payment"
    form_fields: Dict[str, Any] = {"attachment_type_id": attachment_type_id}
    if welfare_payment_id is not None:
        form_fields["welfare_payment_id"] = welfare_payment_id
    if file_payment_id is not None:
        form_fields["file_payment_id"] = file_payment_id
    if upload_batch_id is not None:
        form_fields["upload_batch_id"] = str(upload_batch_id)
    return await _post_evidence_multipart(url, form_fields, file)


@router.get(
    "/v1/case_for_staff/applicant/{applicant_id}/file-payment/{file_payment_id}/file",
    tags=["case_for_staff"],
    summary="ดาวน์โหลด PDF file_payment",
)
async def get_file_payment_for_staff(applicant_id: int, file_payment_id: int) -> Response:
    base = settings.case_service_url.rstrip("/")
    r = await _get_raw(
        f"{base}/v1/case_for_staff/applicant/{applicant_id}/file-payment/{file_payment_id}/file",
    )
    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "application/pdf"),
        headers={
            k: v
            for k, v in r.headers.items()
            if k.lower() in ("content-disposition", "content-length")
        },
    )


@router.get(
    "/v1/case_for_staff/applicant/{applicant_id}/welfare-payments",
    tags=["case_for_staff"],
    summary="รายการ welfare_payment ของ applicant",
)
async def list_welfare_payments_for_staff(
    applicant_id: int,
    dda_ref_id: Optional[int] = Query(None, ge=1),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    url = f"{base}/v1/case_for_staff/applicant/{applicant_id}/welfare-payments"
    if dda_ref_id is not None:
        url = f"{url}?dda_ref_id={dda_ref_id}"
    return await _get(url)


@router.get(
    "/v1/case_for_staff/applicant/{applicant_id}/file-payments",
    tags=["case_for_staff"],
    summary="รายการ file_payment ของ applicant",
)
async def list_file_payments_for_staff(
    applicant_id: int,
    welfare_payment_id: Optional[int] = Query(None, ge=1),
    attachment_type_id: Optional[int] = Query(None, ge=1),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    params: list[str] = []
    if welfare_payment_id is not None:
        params.append(f"welfare_payment_id={welfare_payment_id}")
    if attachment_type_id is not None:
        params.append(f"attachment_type_id={attachment_type_id}")
    url = f"{base}/v1/case_for_staff/applicant/{applicant_id}/file-payments"
    if params:
        url = f"{url}?{'&'.join(params)}"
    return await _get(url)


@router.get(
    "/v1/case_for_staff/applicant/{applicant_id}/payment-upload-history",
    tags=["case_for_staff"],
    summary="ประวัติการอัปโหลด PDF 037/038",
    description=(
        "ส่งต่อ case-service — คืนหมายเลขคำร้อง, ครั้งที่, Payment ID cft037/cft038, "
        "ไฟล์พร้อม view_path ดาวน์โหลด (GET …/file-payment/{id}/file)"
    ),
)
async def get_payment_upload_history_for_staff(applicant_id: int) -> Any:
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/applicant/{applicant_id}/payment-upload-history")


@router.get(
    "/v1/case_for_staff/type-money-categories",
    tags=["case_for_staff"],
    summary="ประเภทเงินช่วยเหลือสำหรับหน้าจอเจ้าหน้าที่",
)
async def list_type_money_categories_for_staff():
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/type-money-categories")


@router.get(
    "/v1/case_for_staff/type-money-categories/{type_money_category_id}",
    tags=["case_for_staff"],
    summary="ดึงประเภทเงินช่วยเหลือตาม id สำหรับหน้าจอเจ้าหน้าที่",
)
async def get_type_money_category_for_staff(type_money_category_id: int):
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/type-money-categories/{type_money_category_id}")


@router.get(
    "/v1/case_for_staff/attachment-types",
    tags=["case_for_staff"],
    summary="ประเภทไฟล์แนบสำหรับหน้าจอเจ้าหน้าที่",
)
async def list_attachment_types_for_staff():
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/attachment-types")


@router.get(
    "/v1/case_for_staff/attachment-types/{attachment_type_id}",
    tags=["case_for_staff"],
    summary="ดึงประเภทไฟล์แนบตาม id สำหรับหน้าจอเจ้าหน้าที่",
)
async def get_attachment_type_for_staff(attachment_type_id: int):
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/attachment-types/{attachment_type_id}")


@router.get(
    "/v1/case_for_staff/current-status",
    tags=["case_for_staff"],
    summary="สถานะคำร้องสำหรับหน้าจอเจ้าหน้าที่",
)
async def list_current_status_for_staff():
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/current-status")


@router.get(
    "/v1/case_for_staff/current-status/{current_status_id}",
    tags=["case_for_staff"],
    summary="ดึงสถานะคำร้องตาม id สำหรับหน้าจอเจ้าหน้าที่",
)
async def get_current_status_for_staff(current_status_id: int):
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/current-status/{current_status_id}")


@router.patch(
    "/v1/case_for_staff/applicant-staff-fields",
    tags=["case_for_staff"],
    summary="อัปเดตประเภทเงิน / ผู้สำรวจ SDSHV (applicants)",
    description=(
        "ส่งต่อ `PATCH …/v1/case_for_staff/applicant-staff-fields?applicant_id=…` — "
        "อัปเดต `type_money_category_id` และ/หรือ `sw_explorer_sdshv` ในตาราง applicants "
        "(คืน process_sla_days และฟิลด์ SLA ที่คำนวณ)"
    ),
    response_model=CaseForStaffApplicantStaffFieldsRead,
)
async def update_case_for_staff_applicant_staff_fields(
    applicant_id: int = Query(..., ge=1, description="id จากตาราง applicants"),
    body: CaseForStaffApplicantStaffFieldsUpdateBody = ...,
) -> CaseForStaffApplicantStaffFieldsRead:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_unset=True)
    data = await _patch(
        f"{base}/v1/case_for_staff/applicant-staff-fields?applicant_id={applicant_id}",
        json=payload,
    )
    return CaseForStaffApplicantStaffFieldsRead.model_validate(data)


@router.patch(
    "/v1/case_for_staff/responsible-division",
    tags=["case_for_staff"],
    summary="อัปเดตหน่วยงานรับผิดชอบ (case_handling.responsible_division_id)",
    response_model=CaseForStaffResponsibleDivisionRead,
)
async def update_case_for_staff_responsible_division(
    applicant_id: int = Query(..., ge=1, description="id จากตาราง applicants"),
    body: CaseForStaffResponsibleDivisionUpdateBody = ...,
) -> CaseForStaffResponsibleDivisionRead:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_unset=True)
    data = await _patch(
        f"{base}/v1/case_for_staff/responsible-division?applicant_id={applicant_id}",
        json=payload,
    )
    return CaseForStaffResponsibleDivisionRead.model_validate(data)


@router.patch(
    "/v1/case_for_staff/case-sections",
    tags=["case_for_staff"],
    summary="นักสังคมฯ แก้ไขส่วนที่ 2–4 ปสค.1",
    description=(
        "ส่งต่อ `PATCH …/v1/case_for_staff/case-sections?applicant_id=…` — "
        "อัปเดต addresses / economic / dependency / household / welfare_history / problem / request_types; "
        "คืน por-kor-1-detail"
    ),
)
async def update_case_for_staff_case_sections(
    applicant_id: int = Query(..., ge=1, description="id จากตาราง applicants"),
    body: StaffCaseSectionsUpdateBody = ...,
) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_unset=True)
    return await _patch(
        f"{base}/v1/case_for_staff/case-sections?applicant_id={applicant_id}",
        json=payload,
    )


@router.post(
    "/v1/case_for_staff/data-edit-log",
    tags=["case_for_staff"],
    summary="บันทึก timeline การแก้ไขข้อมูล (case_data_edit_logs)",
    description=(
        "ส่งต่อ `POST …/v1/case_for_staff/data-edit-log` — "
        "ใช้เมื่อแก้ไขผลการเยี่ยมบ้านหรือกรณีอื่นที่ไม่ผ่าน PATCH /case-sections"
    ),
    status_code=status.HTTP_201_CREATED,
)
async def create_case_for_staff_data_edit_log(body: StaffDataEditLogBody) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_none=True)
    return await _post(f"{base}/v1/case_for_staff/data-edit-log", json=payload)


@router.post(
    "/v1/case_for_staff/welfare-request-status",
    tags=["case_for_staff"],
    summary="บันทึกสถานะคำร้อง (welfare_request_status)",
    description="ส่งต่อ `POST …/v1/case_for_staff/welfare-request-status` — รับ applicant_id และ current_status_id",
    status_code=status.HTTP_201_CREATED,
)
async def create_case_for_staff_welfare_request_status(body: CaseForStaffWelfareRequestStatusBody) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_none=True)
    return await _post(f"{base}/v1/case_for_staff/welfare-request-status", json=payload)


@router.get(
    "/v1/case_for_staff/review-fields",
    tags=["case_for_staff"],
    summary="รายการหัวข้อที่สามารถส่งกลับแก้ไขได้",
    description="ส่งต่อ `GET …/v1/case_for_staff/review-fields` — master data ทุกหัวข้อที่ is_active=true เรียงตาม step, display_order",
)
async def list_review_fields() -> Any:
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/review-fields")


@router.get(
    "/v1/case_for_staff/welfare-edit-request",
    tags=["case_for_staff"],
    summary="ดึง review comments ล่าสุดของ applicant (status=8)",
    description="ส่งต่อ `GET …/v1/case_for_staff/welfare-edit-request?applicant_id=…` — คืน list ของ comment ต่อ field ล่าสุดที่ส่งกลับแก้ไข",
)
async def get_welfare_edit_request_comments(applicant_id: int = Query(..., ge=1)) -> Any:
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/welfare-edit-request?applicant_id={applicant_id}")


@router.post(
    "/v1/case_for_staff/welfare-edit-request",
    tags=["case_for_staff"],
    summary="ส่งคำขอแก้ไขข้อมูล (เปลี่ยนสถานะ 8 + บันทึก comment)",
    description="ส่งต่อ `POST …/v1/case_for_staff/welfare-edit-request` — atomic: สร้าง welfare_request_status(status=8) + welfare_review_comment ต่อหัวข้อ",
    status_code=status.HTTP_201_CREATED,
)
async def create_welfare_edit_request(body: WelfareEditRequestCreateBody) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_none=True)
    return await _post(f"{base}/v1/case_for_staff/welfare-edit-request", json=payload)


@router.get(
    "/v1/case_for_staff/por-kor-1-detail",
    tags=["case_for_staff"],
    summary="รายละเอียดคำร้อง ปศค 1 (รวม path ดึงรูปหลักฐาน)",
    description="ส่งต่อ `GET …/v1/case_for_staff/por-kor-1-detail?applicant_id=…` — ข้อมูลจัดกลุ่ม (บุคคล ที่อยู่ ฯลฯ) พร้อม evidences + view_path",
)
async def get_case_for_staff_por_kor_1_detail(applicant_id: int = Query(..., ge=1)) -> Any:
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/por-kor-1-detail?applicant_id={applicant_id}")


@router.post(
    "/v1/case_for_staff/applicant/{applicant_id}/evidences",
    tags=["case_for_staff"],
    summary="อัปโหลดรูปหลักฐานสำหรับเจ้าหน้าที่",
    description="ส่งต่อ `POST …/v1/case_for_staff/applicant/{applicant_id}/evidences` — เก็บไฟล์รูปลงจานและ welfare_evidences",
)
async def upload_case_for_staff_evidence(
    applicant_id: int,
    attachment_type_id: int = Form(...),
    file_other_type_name: Optional[str] = Form(None),
    household_member_seq: Optional[int] = Form(None, ge=1),
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    base = settings.case_service_url.rstrip("/")
    url = f"{base}/v1/case_for_staff/applicant/{applicant_id}/evidences"
    return await _post_evidence_multipart(
        url,
        {
            "attachment_type_id": attachment_type_id,
            "file_other_type_name": file_other_type_name,
            "household_member_seq": household_member_seq,
        },
        file,
    )


@router.put(
    "/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}",
    tags=["case_for_staff"],
    summary="แก้ไขรูปหลักฐานสำหรับเจ้าหน้าที่",
    description="ส่งต่อ `PUT …/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}` — แทนที่รูปเดิมด้วยรูปใหม่",
)
async def update_case_for_staff_evidence(
    applicant_id: int,
    evidence_id: int,
    attachment_type_id: int = Form(...),
    file_other_type_name: Optional[str] = Form(None),
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    base = settings.case_service_url.rstrip("/")
    url = f"{base}/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}"
    return await _put_evidence_multipart(
        url,
        {
            "attachment_type_id": attachment_type_id,
            "file_other_type_name": file_other_type_name,
        },
        file,
    )


@router.patch(
    "/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}",
    tags=["case_for_staff"],
    summary="แก้ไขชื่อเอกสารสำหรับเจ้าหน้าที่",
    description="ส่งต่อ `PATCH …/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}` — อัปเดต file_other_type_name",
)
async def patch_case_for_staff_evidence(
    applicant_id: int,
    evidence_id: int,
    request: Request,
) -> Any:
    body = await request.json()
    base = settings.case_service_url.rstrip("/")
    return await _patch(
        f"{base}/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}",
        json=body,
    )


@router.delete(
    "/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}",
    tags=["case_for_staff"],
    summary="ลบรูปหลักฐานสำหรับเจ้าหน้าที่",
    description="ส่งต่อ `DELETE …/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}`",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_case_for_staff_evidence(
    applicant_id: int,
    evidence_id: int,
) -> Response:
    base = settings.case_service_url.rstrip("/")
    await _delete(
        f"{base}/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}"
    )
    return Response(status_code=204)


@router.get(
    "/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}/file",
    tags=["case_for_staff"],
    summary="ดาวน์โหลดไฟล์หลักฐานสำหรับเจ้าหน้าที่",
    description="ส่งต่อ `GET …/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}/file`",
)
async def get_case_for_staff_evidence_file(
    applicant_id: int,
    evidence_id: int,
) -> Response:
    base = settings.case_service_url.rstrip("/")
    r = await _get_raw(
        f"{base}/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}/file",
    )
    out_headers: Dict[str, str] = {}
    if cd := r.headers.get("content-disposition"):
        out_headers["content-disposition"] = cd
    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "application/octet-stream"),
        headers=out_headers,
    )


@router.post(
    "/v1/case_for_staff/welfare-dda-ref",
    tags=["case_for_staff"],
    summary="สร้าง welfare_dda_ref และ welfare_payment",
    description=(
        "ส่งต่อ `POST …/v1/case_for_staff/welfare-dda-ref` — หนึ่ง dda_ref ผูก welfare_payment หลาย applicant; "
        "ฟิลด์จ่ายเงินบน payment ว่างไว้สำหรับอัปเดตภายหลัง"
    ),
    status_code=status.HTTP_201_CREATED,
)
async def create_welfare_dda_ref_bundle(body: WelfareDdaRefBundleCreateBody) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_none=True)
    return await _post(f"{base}/v1/case_for_staff/welfare-dda-ref", json=payload)


@router.post(
    "/v1/case_for_staff/approve-case",
    tags=["case_for_staff"],
    summary="บันทึกการอนุมัติเคส (approve_case)",
    description="ส่งต่อ `POST …/v1/case_for_staff/approve-case` — บันทึกข้อมูลประวัติ ลายเซ็นอิเล็กทรอนิกส์",
    status_code=status.HTTP_201_CREATED,
)
async def create_approve_case_for_staff(body: ApproveCaseCreateBody) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_none=True)
    return await _post(f"{base}/v1/case_for_staff/approve-case", json=payload)


@router.get(
    "/v1/case_for_staff/approve-case",
    tags=["case_for_staff"],
    summary="ดึงประวัติการอนุมัติเคส",
    description="ส่งต่อ `GET …/v1/case_for_staff/approve-case?applicant_id=…` — คืนประวัติล่าสุดของเคส",
)
async def list_approve_case_for_staff(applicant_id: int = Query(..., ge=1)) -> Any:
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/approve-case?applicant_id={applicant_id}")


@router.get(
    "/v1/case_for_staff/article",
    tags=["case_for_staff"],
    summary="ดึง article ตาม applicant_id",
    description="ส่งต่อ `GET …/v1/case_for_staff/article?applicant_id=…` — 404 เมื่อยังไม่มี article",
)
async def get_article_for_staff(applicant_id: int = Query(..., ge=1)) -> Any:
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/article?applicant_id={applicant_id}")


@router.post(
    "/v1/case_for_staff/article",
    tags=["case_for_staff"],
    summary="บันทึก article (ครั้งแรก)",
    description=(
        "ส่งต่อ `POST …/v1/case_for_staff/article` — สร้างเนื้อหา article อย่างเดียว. "
        "อนุมัติ/เปลี่ยนสถานะใช้ POST /v1/case_for_staff/approve-case"
    ),
    status_code=status.HTTP_201_CREATED,
)
async def create_article_for_staff(body: ArticleCreateBody) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_none=True, mode="json")
    return await _post(f"{base}/v1/case_for_staff/article", json=payload)


@router.patch(
    "/v1/case_for_staff/article",
    tags=["case_for_staff"],
    summary="อัปเดต article (ไม่เปลี่ยนสถานะ)",
    description="ส่งต่อ `PATCH …/v1/case_for_staff/article?applicant_id=…` — แก้ฟิลด์เนื้อหา article อย่างเดียว",
)
async def patch_article_for_staff(
    applicant_id: int = Query(..., ge=1),
    body: ArticleUpdateBody = Body(...),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_unset=True, mode="json")
    return await _patch(
        f"{base}/v1/case_for_staff/article?applicant_id={applicant_id}",
        json=payload,
    )


@router.post(
    "/v1/case_for_staff/cover-document-batch",
    tags=["case_for_staff"],
    summary="สร้าง cover document batch",
    status_code=status.HTTP_201_CREATED,
)
async def create_cover_document_batch_for_staff(body: CoverDocumentBatchCreateBody) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_none=True, mode="json")
    return await _post(f"{base}/v1/case_for_staff/cover-document-batch", json=payload)


@router.patch(
    "/v1/case_for_staff/cover-document-batch/{batch_id}",
    tags=["case_for_staff"],
    summary="แก้ header cover document batch",
)
async def patch_cover_document_batch_for_staff(
    batch_id: int,
    body: CoverDocumentBatchUpdateBody = Body(...),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(exclude_unset=True, mode="json")
    return await _patch(
        f"{base}/v1/case_for_staff/cover-document-batch/{batch_id}",
        json=payload,
    )


@router.get(
    "/v1/case_for_staff/cover-document-batch/{batch_id}",
    tags=["case_for_staff"],
    summary="ดึง cover document batch",
)
async def get_cover_document_batch_for_staff(batch_id: int) -> Any:
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/cover-document-batch/{batch_id}")


@router.get(
    "/v1/case_for_staff/cover-document-batch",
    tags=["case_for_staff"],
    summary="รายการ cover document batch",
)
async def list_cover_document_batches_for_staff(
    province_id: Optional[int] = Query(None, ge=1),
    pending: bool = Query(False),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    params = {}
    if province_id is not None:
        params["province_id"] = province_id
    if pending:
        params["pending"] = "true"
    suffix = f"?{urlencode(params)}" if params else ""
    return await _get(f"{base}/v1/case_for_staff/cover-document-batch{suffix}")


@router.get(
    "/v1/case_for_staff/applicant/{applicant_id}/more-mso",
    tags=["case_for_staff"],
    summary="ดึงข้อมูล MSO เพิ่มเติมของ applicant",
    description="ส่งต่อ `GET …/v1/case_for_staff/applicant/{applicant_id}/more-mso` — คืน null ถ้ายังไม่มี",
)
async def get_more_mso_for_staff(applicant_id: int) -> Any:
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/applicant/{applicant_id}/more-mso")


@router.put(
    "/v1/case_for_staff/applicant/{applicant_id}/more-mso",
    tags=["case_for_staff"],
    summary="สร้างหรืออัปเดตข้อมูล MSO เพิ่มเติม (upsert)",
    description="ส่งต่อ `PUT …/v1/case_for_staff/applicant/{applicant_id}/more-mso` — upsert แถว more_mso",
)
async def upsert_more_mso_for_staff(
    applicant_id: int,
    body: MoreMsoUpsertBody = Body(...),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(mode="json")
    return await _put(f"{base}/v1/case_for_staff/applicant/{applicant_id}/more-mso", json=payload)


@router.get(
    "/v1/case_for_staff/applicant/{applicant_id}/mso-forward-status",
    tags=["case_for_staff"],
    summary="ตรวจสถานะการส่งต่อกระทรวง / MSO logbook",
    description=(
        "ส่งต่อ `GET …/v1/case_for_staff/applicant/{applicant_id}/mso-forward-status` — "
        "ใช้ disabled ปุ่มส่งต่อเมื่อ `ministry.sent` หรือ `logbook.sent` เป็น true"
    ),
)
async def get_mso_forward_status_for_staff(applicant_id: int) -> Any:
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/case_for_staff/applicant/{applicant_id}/mso-forward-status")


@router.post(
    "/v1/case_for_staff/applicant/{applicant_id}/mso-forward",
    tags=["case_for_staff"],
    status_code=201,
    summary="บันทึกการส่งต่อ (กระทรวง หรือ MSO logbook)",
    description=(
        "ส่งต่อ `POST …/v1/case_for_staff/applicant/{applicant_id}/mso-forward` — "
        "body ใช้ `send_channel`: `ministry` | `logbook`"
    ),
)
async def create_mso_forward_for_staff(
    applicant_id: int,
    body: MsoForwardCreateBody = Body(...),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(mode="json")
    return await _post(f"{base}/v1/case_for_staff/applicant/{applicant_id}/mso-forward", json=payload)


@router.get(
    "/v1/cases/{applicant_id}",
    tags=["cases"],
    summary="ดึงคำร้องตาม applicant_id",
    description="ส่งต่อ `GET …/v1/cases/{applicant_id}` (ตัวอ้างอิงคือ id จากตาราง applicants)",
)
async def get_case(
    applicant_id: int,
    auth: CitizenOrVsmartAuth = Depends(require_citizen_or_vsmart_compat),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    if auth.mode == "vsmart":
        detail = await _get(
            f"{base}/v1/case_for_staff/por-kor-1-detail?applicant_id={applicant_id}",
            headers=vsmart_internal_headers(),
        )
        return case_compat_from_por_kor_1(detail, applicant_id)
    return await _get(
        f"{base}/v1/cases/{applicant_id}",
        headers=_forward_auth_headers(auth.authorization),
    )


@router.put(
    "/v1/cases/{applicant_id}/evidences/{evidence_id}",
    tags=["cases"],
    summary="แก้ไขรูปหลักฐาน (multipart)",
    description="ส่งต่อ `PUT …/v1/cases/{applicant_id}/evidences/{evidence_id}` — แทนที่รูปเดิมด้วยรูปใหม่",
)
async def update_case_evidence(
    applicant_id: int,
    evidence_id: int,
    attachment_type_id: int = Form(...),
    file_other_type_name: Optional[str] = Form(None),
    file: UploadFile = File(...),
    auth: CitizenOrVsmartAuth = Depends(require_citizen_or_vsmart_compat),
) -> Dict[str, Any]:
    base = settings.case_service_url.rstrip("/")
    if auth.mode == "vsmart":
        url = staff_evidence_url(base, applicant_id, evidence_id)
        headers = vsmart_internal_headers()
    else:
        url = f"{base}/v1/cases/{applicant_id}/evidences/{evidence_id}"
        headers = _forward_auth_headers(auth.authorization)
    return await _put_evidence_multipart(
        url,
        {
            "attachment_type_id": attachment_type_id,
            "file_other_type_name": file_other_type_name,
        },
        file,
        headers=headers,
    )


@router.patch(
    "/v1/cases/{applicant_id}",
    tags=["cases"],
    summary="แก้ไขข้อมูล case ที่มีอยู่แล้ว",
    description="ส่งต่อ `PATCH …/v1/cases/{applicant_id}` ใน case-service — ส่งเฉพาะ section ที่ต้องการแก้ไข",
)
async def update_case(
    applicant_id: int,
    request: Request,
    authorization: str = Depends(require_citizen_bearer),
) -> Any:
    body = await request.json()
    base = settings.case_service_url.rstrip("/")
    return await _patch(
        f"{base}/v1/cases/{applicant_id}",
        json=body,
        headers=_forward_auth_headers(authorization),
    )


@router.post(
    "/v1/cases/{applicant_id}/resubmit",
    tags=["cases"],
    summary="ยืนยันคำร้องหลังแก้ไขข้อมูลที่ถูกตีกลับ",
    description=(
        "ส่งต่อ `POST …/v1/cases/{applicant_id}/resubmit` ใน case-service — "
        "reset สถานะกลับเป็น 'รอรับเรื่อง' หลังประชาชนแก้ไขข้อมูลที่ถูกตีกลับเสร็จแล้ว"
    ),
)
async def resubmit_case(
    applicant_id: int,
    authorization: str = Depends(require_citizen_bearer),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    return await _post(
        f"{base}/v1/cases/{applicant_id}/resubmit",
        json={},
        headers=_forward_auth_headers(authorization),
    )


@router.patch(
    "/v1/cases/{applicant_id}/evidences/{evidence_id}",
    tags=["cases"],
    summary="แก้ไขชื่อเอกสาร",
    description="ส่งต่อ `PATCH …/v1/cases/{applicant_id}/evidences/{evidence_id}` ใน case-service — อัปเดต file_other_type_name",
)
async def patch_case_evidence(
    applicant_id: int,
    evidence_id: int,
    request: Request,
    auth: CitizenOrVsmartAuth = Depends(require_citizen_or_vsmart_compat),
) -> Any:
    body = await request.json()
    base = settings.case_service_url.rstrip("/")
    if auth.mode == "vsmart":
        url = staff_evidence_url(base, applicant_id, evidence_id)
        headers = vsmart_internal_headers()
    else:
        url = f"{base}/v1/cases/{applicant_id}/evidences/{evidence_id}"
        headers = _forward_auth_headers(auth.authorization)
    return await _patch(url, json=body, headers=headers)


@router.delete(
    "/v1/cases/{applicant_id}/evidences/{evidence_id}",
    tags=["cases"],
    summary="ลบหลักฐาน (รูป)",
    description="ส่งต่อ `DELETE …/v1/cases/{applicant_id}/evidences/{evidence_id}` ใน case-service — ลบทั้ง DB record และไฟล์บน disk",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_case_evidence(
    applicant_id: int,
    evidence_id: int,
    auth: CitizenOrVsmartAuth = Depends(require_citizen_or_vsmart_compat),
) -> Response:
    base = settings.case_service_url.rstrip("/")
    if auth.mode == "vsmart":
        url = staff_evidence_url(base, applicant_id, evidence_id)
        headers = vsmart_internal_headers()
    else:
        url = f"{base}/v1/cases/{applicant_id}/evidences/{evidence_id}"
        headers = _forward_auth_headers(auth.authorization)
    await _delete(url, headers=headers)
    return Response(status_code=204)


@router.get(
    "/v1/cases/{applicant_id}/evidences/{evidence_id}/file",
    tags=["cases"],
    summary="ดาวน์โหลดไฟล์หลักฐาน (รูป)",
    description="ส่งต่อ `GET …/v1/cases/{applicant_id}/evidences/{evidence_id}/file` ใน case-service",
)
async def get_case_evidence_file(
    applicant_id: int,
    evidence_id: int,
    auth: CitizenOrVsmartAuth = Depends(require_citizen_or_vsmart_compat),
) -> Response:
    base = settings.case_service_url.rstrip("/")
    if auth.mode == "vsmart":
        url = staff_evidence_url(base, applicant_id, evidence_id, file=True)
        headers = vsmart_internal_headers()
    else:
        url = f"{base}/v1/cases/{applicant_id}/evidences/{evidence_id}/file"
        headers = _forward_auth_headers(auth.authorization)
    r = await _get_raw(url, headers=headers)
    out_headers: Dict[str, str] = {}
    if cd := r.headers.get("content-disposition"):
        out_headers["content-disposition"] = cd
    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "application/octet-stream"),
        headers=out_headers,
    )


@router.delete(
    "/v1/applicants/by-cid",
    tags=["applicants"],
    summary="ลบ applicants ตามเลขบัตรประชาชน",
    description=(
        "ส่งต่อ `DELETE …/v1/applicants/by-cid?cid=…` ใน case-service — "
        "ลบ applicants, ข้อมูลตารางย่อยที่อ้าง applicant_id และข้อมูลใน "
        "`screening_logs` / `welfare_request_consents` ของบุคคลนั้น"
    ),
    response_model=ApplicantDeleteByCidResponse,
)
async def delete_applicants_by_cid(
    cid: str = Query(..., min_length=13, max_length=13, description="เลขบัตรประชาชน 13 หลัก"),
    authorization: str = Depends(require_citizen_bearer),
) -> ApplicantDeleteByCidResponse:
    base = settings.case_service_url.rstrip("/")
    data = await _delete(
        f"{base}/v1/applicants/by-cid?cid={cid}",
        timeout=120.0,
        headers=_forward_auth_headers(authorization),
    )
    return ApplicantDeleteByCidResponse.model_validate(data)


@router.delete(
    "/v1/citizen/person",
    tags=["persons"],
    summary="PDPA — ลบตัวตนในระบบ (ประชาชน)",
    response_model=PersonDeleteByCidResponse,
)
async def delete_citizen_person(
    cid: str = Query(..., min_length=13, max_length=13),
    authorization: str = Depends(require_citizen_bearer),
) -> PersonDeleteByCidResponse:
    base = settings.case_service_url.rstrip("/")
    data = await _delete(
        f"{base}/v1/citizen/person?cid={cid}",
        timeout=120.0,
        headers=_forward_auth_headers(authorization),
    )
    return PersonDeleteByCidResponse.model_validate(data)


@router.delete(
    "/v1/admin/persons/by-cid",
    tags=["admin", "persons"],
    summary="Admin — ลบ person ตาม cid",
    response_model=PersonDeleteByCidResponse,
)
async def admin_delete_person_by_cid(
    cid: str = Query(..., min_length=13, max_length=13),
    authorization: str = Depends(require_admin_bearer),
) -> PersonDeleteByCidResponse:
    base = settings.case_service_url.rstrip("/")
    data = await _delete(
        f"{base}/v1/admin/persons/by-cid?cid={cid}",
        timeout=120.0,
        headers=_forward_auth_headers(authorization),
    )
    return PersonDeleteByCidResponse.model_validate(data)


@router.get(
    "/v1/screening-logs/latest-passed",
    tags=["eligibility"],
    summary="ดึง screening log ล่าสุดที่ผ่านเกณฑ์",
    response_model=Optional[ScreeningLogReadResponse],
)
async def bff_get_latest_passed_screening_log(
    person_id: int = Query(..., description="ID ของ person"),
    authorization: str = Depends(require_citizen_bearer),
) -> Optional[ScreeningLogReadResponse]:
    """ส่งต่อไปยัง case-service — คืน null ถ้ายังไม่เคยผ่านเกณฑ์."""
    base = settings.case_service_url.rstrip("/")
    data = await _get(
        f"{base}/v1/screening-logs/latest-passed?person_id={person_id}",
        headers=_forward_auth_headers(authorization),
    )
    if data is None:
        return None
    return ScreeningLogReadResponse.model_validate(data)


@router.post(
    "/v1/screening-logs",
    tags=["eligibility"],
    summary="บันทึก screening_logs",
    description="ส่งต่อไปยัง case-service `POST /v1/screening-logs` (คัดกรองสิทธิ์เบื้องต้น)",
    response_model=ScreeningLogReadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bff_create_screening_log(
    request: Request,
    body: ScreeningLogCreateRequest,
    authorization: str = Depends(require_citizen_bearer),
) -> ScreeningLogReadResponse:
    """รับข้อมูลคัดกรองแล้วส่งต่อ POST ไป case-service พร้อม inject ip_address จาก request."""
    # ดึง IP จาก X-Forwarded-For (กรณีผ่าน reverse proxy) หรือ client.host
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    client_ip = forwarded or (request.client.host if request.client else None)

    payload = body.model_dump()
    payload["ip_address"] = client_ip  # override ค่าที่ frontend ส่งมา (มักเป็น null)

    data = await _post(
        f"{settings.case_service_url.rstrip('/')}/v1/screening-logs",
        json=payload,
        headers=_forward_auth_headers(authorization),
    )
    return ScreeningLogReadResponse.model_validate(data)


@router.post(
    "/v1/welfare-request-consents",
    tags=["eligibility"],
    summary="บันทึก welfare_request_consents",
    description="ส่งต่อไปยัง case-service `POST /v1/welfare-request-consents` (ความยินยอมเบื้องต้น)",
    response_model=WelfareRequestConsentReadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bff_create_welfare_request_consent(
    body: WelfareRequestConsentCreateRequest,
    authorization: str = Depends(require_citizen_bearer),
) -> WelfareRequestConsentReadResponse:
    """รับความยินยอมแล้วส่งต่อ POST ไป case-service."""
    data = await _post(
        f"{settings.case_service_url.rstrip('/')}/v1/welfare-request-consents",
        json=body.model_dump(),
        headers=_forward_auth_headers(authorization),
    )
    return WelfareRequestConsentReadResponse.model_validate(data)


def _case_lookup_url(path_under_v1: str) -> str:
    """path_under_v1 เช่น 'v1/lookups/prefix-types' — path parameter ต้องตรงกับ case-service ทุกตัว"""
    base = settings.case_service_url.rstrip("/")
    return f"{base}/{path_under_v1.lstrip('/')}"


# --- intake: บันทึก/แก้ไขข้อมูลการรับเรื่อง (หน้า 11, 13, 20) ---


@router.get(
    "/v1/intake/regulations",
    tags=["intake"],
    summary="รายการระเบียบสำหรับ dropdown หน้า 11",
)
async def bff_list_regulations(
    citizen: Optional[str] = Query(None),
    budget_year: Optional[int] = Query(None),
):
    base = settings.case_service_url.rstrip("/")
    params = {}
    if citizen is not None:
        params["citizen"] = citizen
    if budget_year is not None:
        params["budget_year"] = budget_year
    query_string = urlencode(params)
    url = f"{base}/v1/intake/regulations?{query_string}" if query_string else f"{base}/v1/intake/regulations"
    return await _get(url)


@router.get(
    "/v1/intake/regulations/{regulation_id}",
    tags=["intake"],
    summary="รายละเอียดระเบียบ",
)
async def bff_get_regulation(regulation_id: int):
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/intake/regulations/{regulation_id}")


@router.get(
    "/v1/intake/payment-methods",
    tags=["intake"],
    summary="รายการวิธีจ่ายเงินสำหรับ dropdown หน้า 13",
)
async def bff_list_payment_methods():
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/intake/payment-methods")


@router.get(
    "/v1/intake/cases/{applicant_id}",
    tags=["intake"],
    summary="ดูสถานะ intake ทั้งหมด (หน้า 11, 13, 20)",
)
async def bff_get_intake(applicant_id: int):
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/intake/cases/{applicant_id}")


@router.post(
    "/v1/intake/cases/{applicant_id}",
    tags=["intake"],
    summary="บันทึกข้อมูลหน้า 11 (eleven_insert) — upsert case_handling + regulation_choice",
)
async def bff_upsert_intake_handling(applicant_id: int, request: Request):
    body = await request.json()
    base = settings.case_service_url.rstrip("/")
    return await _post(f"{base}/v1/intake/cases/{applicant_id}", json=body)


@router.patch(
    "/v1/intake/cases/{applicant_id}",
    tags=["intake"],
    summary="แก้ไขข้อมูลหน้า 11",
)
async def bff_patch_intake_handling(applicant_id: int, request: Request):
    body = await request.json()
    base = settings.case_service_url.rstrip("/")
    return await _patch(f"{base}/v1/intake/cases/{applicant_id}", json=body)


@router.post(
    "/v1/intake/cases/{applicant_id}/payment",
    tags=["intake"],
    summary="บันทึกวิธีจ่ายเงินหน้า 13",
)
async def bff_upsert_intake_payment(applicant_id: int, request: Request):
    body = await request.json()
    base = settings.case_service_url.rstrip("/")
    return await _post(f"{base}/v1/intake/cases/{applicant_id}/payment", json=body)


@router.get(
    "/v1/intake/cases/{applicant_id}/payment",
    tags=["intake"],
    summary="ดูข้อมูลวิธีจ่ายเงิน (case_payment)",
)
async def bff_get_intake_payment(applicant_id: int):
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/intake/cases/{applicant_id}/payment")


@router.patch(
    "/v1/intake/cases/{applicant_id}/payment",
    tags=["intake"],
    summary="แก้ไขวิธีจ่ายเงิน (case_payment)",
)
async def bff_patch_intake_payment(applicant_id: int, request: Request):
    body = await request.json()
    base = settings.case_service_url.rstrip("/")
    return await _patch(f"{base}/v1/intake/cases/{applicant_id}/payment", json=body)


@router.post(
    "/v1/intake/cases/{applicant_id}/ktb",
    tags=["intake"],
    summary="บันทึก KTB Corporate Online หน้า 20",
)
async def bff_upsert_intake_ktb(applicant_id: int, request: Request):
    body = await request.json()
    base = settings.case_service_url.rstrip("/")
    return await _post(f"{base}/v1/intake/cases/{applicant_id}/ktb", json=body)


@router.get(
    "/v1/intake/cases/{applicant_id}/ktb",
    tags=["intake"],
    summary="ดูข้อมูล KTB Corporate (case_ktb_corporate)",
)
async def bff_get_intake_ktb(applicant_id: int):
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/intake/cases/{applicant_id}/ktb")


@router.patch(
    "/v1/intake/cases/{applicant_id}/ktb",
    tags=["intake"],
    summary="แก้ไขข้อมูล KTB Corporate",
)
async def bff_patch_intake_ktb(applicant_id: int, request: Request):
    body = await request.json()
    base = settings.case_service_url.rstrip("/")
    return await _patch(f"{base}/v1/intake/cases/{applicant_id}/ktb", json=body)


@router.get(
    "/v1/intake/cases/{applicant_id}/diagnoses",
    tags=["intake"],
    summary="รายการคำวินิจฉัยทั้งหมดของเคส (BR-DIAG-01)",
)
async def bff_list_case_diagnoses(
    applicant_id: int,
    actor_user_id: Optional[int] = Query(None),
):
    base = settings.case_service_url.rstrip("/")
    url = f"{base}/v1/intake/cases/{applicant_id}/diagnoses"
    if actor_user_id is not None:
        url = f"{url}?actor_user_id={actor_user_id}"
    return await _get(url)


@router.post(
    "/v1/intake/cases/{applicant_id}/diagnoses",
    tags=["intake"],
    summary="เพิ่มคำวินิจฉัยของ user ตนเอง (BR-DIAG-02)",
    status_code=status.HTTP_201_CREATED,
)
async def bff_create_case_diagnosis(applicant_id: int, request: Request):
    body = await request.json()
    base = settings.case_service_url.rstrip("/")
    return await _post(f"{base}/v1/intake/cases/{applicant_id}/diagnoses", json=body)


@router.patch(
    "/v1/intake/cases/{applicant_id}/diagnoses/{diagnosis_id}",
    tags=["intake"],
    summary="แก้ไขคำวินิจฉัยของตนเอง (BR-DIAG-04, 05, 06)",
)
async def bff_update_case_diagnosis(
    applicant_id: int, diagnosis_id: int, request: Request
):
    body = await request.json()
    base = settings.case_service_url.rstrip("/")
    return await _patch(
        f"{base}/v1/intake/cases/{applicant_id}/diagnoses/{diagnosis_id}", json=body
    )


@router.get(
    "/v1/intake/cases/{applicant_id}/diagnoses/{diagnosis_id}/history",
    tags=["intake"],
    summary="ประวัติการแก้ไขคำวินิจฉัย (BR-DIAG-06)",
)
async def bff_case_diagnosis_history(applicant_id: int, diagnosis_id: int):
    base = settings.case_service_url.rstrip("/")
    return await _get(
        f"{base}/v1/intake/cases/{applicant_id}/diagnoses/{diagnosis_id}/history"
    )


# --- lookups: เส้นและชื่อพารามิเตอร์ตรงกับ case-service (ไม่ใช้ query บอกประเภท master) ---


@router.get(
    "/v1/lookups/prefix-types",
    tags=["lookups"],
    summary="รายการคำนำหน้าชื่อ",
    description="ส่งต่อ `GET .../v1/lookups/prefix-types`",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_prefix_types():
    return await _get(_case_lookup_url("v1/lookups/prefix-types"))


@router.get(
    "/v1/lookups/prefix-types/{prefix_type_id}",
    tags=["lookups"],
    summary="ดึงคำนำหน้าชื่อตาม id",
    description="ส่งต่อ `GET .../v1/lookups/prefix-types/{prefix_type_id}`",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_prefix_type(prefix_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/prefix-types/{prefix_type_id}"))


@router.get(
    "/v1/lookups/received-welfare-types",
    tags=["lookups"],
    summary="ประเภทสวัสดิการที่เคยได้รับ",
    description="ส่งต่อ `GET .../v1/lookups/received-welfare-types`",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_received_welfare_types():
    return await _get(_case_lookup_url("v1/lookups/received-welfare-types"))


@router.get(
    "/v1/lookups/received-welfare-types/{received_welfare_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทสวัสดิการที่เคยได้รับตาม id",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_received_welfare_type(received_welfare_type_id: int):
    return await _get(
        _case_lookup_url(f"v1/lookups/received-welfare-types/{received_welfare_type_id}")
    )


@router.get(
    "/v1/lookups/attachment-types",
    tags=["lookups"],
    summary="ประเภทรูปภาพ / เอกสารแนบ",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_attachment_types():
    return await _get(_case_lookup_url("v1/lookups/attachment-types"))


@router.get(
    "/v1/lookups/attachment-types/{attachment_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทเอกสารแนบตาม id",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_attachment_type(attachment_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/attachment-types/{attachment_type_id}"))


@router.get(
    "/v1/lookups/attachment_types",
    tags=["lookups"],
    summary="ประเภทรูปภาพ / เอกสารแนบ (alias ชื่อตาราง)",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_attachment_types_snake():
    return await _get(_case_lookup_url("v1/lookups/attachment_types"))


@router.get(
    "/v1/lookups/attachment_types/{attachment_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทเอกสารแนบตาม id (alias ชื่อตาราง)",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_attachment_type_snake(attachment_type_id: int):
    return await _get(
        _case_lookup_url(f"v1/lookups/attachment_types/{attachment_type_id}")
    )


@router.get(
    "/v1/lookups/current-status",
    tags=["lookups"],
    summary="สถานะคำร้อง",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_current_status():
    return await _get(_case_lookup_url("v1/lookups/current-status"))


@router.get(
    "/v1/lookups/current-status/{current_status_id}",
    tags=["lookups"],
    summary="ดึงสถานะคำร้องตาม id",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_current_status(current_status_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/current-status/{current_status_id}"))


@router.get(
    "/v1/lookups/request-types",
    tags=["lookups"],
    summary="ประเภทความช่วยเหลือ / คำร้อง",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_request_types():
    return await _get(_case_lookup_url("v1/lookups/request-types"))


@router.get(
    "/v1/lookups/request-types/{request_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทคำร้องตาม id",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_request_type(request_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/request-types/{request_type_id}"))


@router.get(
    "/v1/lookups/marital-status-types",
    tags=["lookups"],
    summary="สถานภาพสมรส",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_marital_status_types():
    return await _get(_case_lookup_url("v1/lookups/marital-status-types"))


@router.get(
    "/v1/lookups/marital-status-types/{marital_status_type_id}",
    tags=["lookups"],
    summary="ดึงสถานภาพสมรสตาม id",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_marital_status_type(marital_status_type_id: int):
    return await _get(
        _case_lookup_url(f"v1/lookups/marital-status-types/{marital_status_type_id}")
    )


@router.get(
    "/v1/lookups/housing-types",
    tags=["lookups"],
    summary="สภาพที่อยู่อาศัย",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_housing_types():
    return await _get(_case_lookup_url("v1/lookups/housing-types"))


@router.get(
    "/v1/lookups/housing-types/{housing_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทที่อยู่อาศัยตาม id",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_housing_type(housing_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/housing-types/{housing_type_id}"))


@router.get(
    "/v1/lookups/income-source-types",
    tags=["lookups"],
    summary="ประเภทของรายได้",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_income_source_types():
    return await _get(_case_lookup_url("v1/lookups/income-source-types"))


@router.get(
    "/v1/lookups/income-source-types/{income_source_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทแหล่งรายได้ตาม id",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_income_source_type(income_source_type_id: int):
    return await _get(
        _case_lookup_url(f"v1/lookups/income-source-types/{income_source_type_id}")
    )


@router.get(
    "/v1/lookups/dependency-types",
    tags=["lookups"],
    summary="ประเภทผู้อุปการะ",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_dependency_types():
    return await _get(_case_lookup_url("v1/lookups/dependency-types"))


@router.get(
    "/v1/lookups/dependency-types/{dependency_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทผู้อุปการะตาม id",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_dependency_type(dependency_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/dependency-types/{dependency_type_id}"))


@router.get(
    "/v1/lookups/address-types",
    tags=["lookups"],
    summary="ประเภทที่อยู่",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_address_types():
    return await _get(_case_lookup_url("v1/lookups/address-types"))


@router.get(
    "/v1/lookups/address-types/{address_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทที่อยู่ตาม id",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_address_type(address_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/address-types/{address_type_id}"))


@router.get("/v1/lookups/requester-relation-types", 
    tags=["lookups"], 
    summary="ประเภทความสัมพันธ์ผู้ร้องขอ", 
    description="ส่งต่อไปยัง case-service `GET /v1/lookups/requester-relation-types`",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_requester_relation_types():
    return await _get(_case_lookup_url("v1/lookups/requester-relation-types"))


@router.get("/v1/lookups/requester-relation-types/{requester-relation_type_id}", 
    tags=["lookups"], 
    summary="ดึงประเภทความสัมพันธ์ผู้ร้องขอตาม id", 
    description="ส่งต่อไปยัง case-service `GET /v1/lookups/requester-relation-types/{requester-relation_type_id}`",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_requester_relation_type(requester_relation_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/requester-relation-types/{requester_relation_type_id}"))

@router.get(
    "/v1/lookups/bank-names",
    tags=["lookups"],
    summary="รายการชื่อธนาคาร",
    description=(
        "ส่งต่อ `GET .../v1/lookups/bank-names` — เรียงตาม `order` แล้ว `id`; "
        "แต่ละรายการมี `bank_id_mso`, `bank_code`, `order`"
    ),
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_bank_names():
    return await _get(_case_lookup_url("v1/lookups/bank-names"))


@router.get(
    "/v1/lookups/bank-names/{bank_name_id}",
    tags=["lookups"],
    summary="ดึงชื่อธนาคารตาม id",
    description=(
        "ส่งต่อ `GET .../v1/lookups/bank-names/{bank_name_id}` — "
        "รวม `bank_id_mso`, `bank_code`, `order`"
    ),
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_bank_name(bank_name_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/bank-names/{bank_name_id}"))


@router.get(
    "/v1/lookups/bank-account-types",
    tags=["lookups"],
    summary="รายการประเภทบัญชีธนาคาร",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_bank_account_types():
    return await _get(_case_lookup_url("v1/lookups/bank-account-types"))


@router.get(
    "/v1/lookups/bank-account-types/{bank_account_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทบัญชีธนาคารตาม id",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_bank_account_type(bank_account_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/bank-account-types/{bank_account_type_id}"))


@router.get(
    "/v1/lookups/household-member-relation-types",
    tags=["lookups"],
    summary="ความสัมพันธ์กับผู้ประสบปัญหา (บิดา/มารดา, บุตร, คู่สมรส ฯลฯ)",
    description="ส่งต่อ `GET .../v1/lookups/household-member-relation-types`",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_household_member_relation_types():
    return await _get(_case_lookup_url("v1/lookups/household-member-relation-types"))


@router.get(
    "/v1/lookups/household-member-relation-types/{relation_type_id}",
    tags=["lookups"],
    summary="ดึงความสัมพันธ์กับผู้ประสบปัญหาตาม id",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_household_member_relation_type(relation_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/household-member-relation-types/{relation_type_id}"))


@router.get(
    "/v1/lookups/hardship-status-types",
    tags=["lookups"],
    summary="สถานะความเดือดร้อน (ประสบปัญหาเอง / ครอบครัวประสบปัญหา)",
    description="ส่งต่อ `GET .../v1/lookups/hardship-status-types`",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_hardship_status_types():
    return await _get(_case_lookup_url("v1/lookups/hardship-status-types"))


@router.get(
    "/v1/lookups/hardship-status-types/{hardship_status_type_id}",
    tags=["lookups"],
    summary="ดึงสถานะความเดือดร้อนตาม id",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_hardship_status_type(hardship_status_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/hardship-status-types/{hardship_status_type_id}"))


@router.get(
    "/v1/lookups/occupation-types",
    tags=["lookups"],
    summary="ประเภทอาชีพ (นักเรียน / เกษตรกร / รับจ้าง / อื่นๆ ฯลฯ)",
    description="ส่งต่อ `GET .../v1/lookups/occupation-types`",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_occupation_types():
    return await _get(_case_lookup_url("v1/lookups/occupation-types"))


@router.get(
    "/v1/lookups/occupation-types/{occupation_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทอาชีพตาม id",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_occupation_type(occupation_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/occupation-types/{occupation_type_id}"))


@router.get(
    "/v1/geo/provinces",
    tags=["geo"],
    summary="รายการจังหวัด",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_provinces():
    return await _get(_case_lookup_url("v1/geo/provinces"))


@router.get(
    "/v1/geo/provinces/{province_id}",
    tags=["geo"],
    summary="ดึงจังหวัดตาม id",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_get_province(province_id: int):
    return await _get(_case_lookup_url(f"v1/geo/provinces/{province_id}"))


@router.get(
    "/v1/geo/districts",
    tags=["geo"],
    summary="รายการอำเภอในจังหวัด",
    description="ต้องส่ง query `province_id` — ส่งต่อไป case-service",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_districts(province_id: int = Query(..., description="รหัสจังหวัด")):
    return await _get(_case_lookup_url(f"v1/geo/districts?province_id={province_id}"))


@router.get(
    "/v1/geo/sub-districts",
    tags=["geo"],
    summary="รายการตำบลในอำเภอ พร้อมรหัสไปรษณีย์และแถว sub_districts_postcode",
    description="ต้องส่ง query `district_id` — response มี `sub_districts_postcode` (id bridge) สำหรับบันทึกที่อยู่",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def bff_list_sub_districts(district_id: int = Query(..., description="รหัสอำเภอ")):
    return await _get(_case_lookup_url(f"v1/geo/sub-districts?district_id={district_id}"))


class CreateNotificationRequest(BaseModel):
    """โครงสร้าง body สำหรับสร้างการแจ้งเตือนที่ส่งต่อไป notification-service."""

    idempotency_key: str
    channel: str
    to: str
    template_code: str
    payload: Dict[str, Any] = {}


class ThaidLoginBody(BaseModel):
    """ส่งต่อไป thaid-auth-service — ใช้ `post_login_redirect` เมื่อต้องการ 302 กลับหน้าแอปหลังล็อกอิน."""

    post_login_redirect: Optional[str] = None
    browser_oauth_base: Optional[str] = Field(
        default=None,
        description="ฐาน URL ที่เบราว์เซอร์เรียก BFF ได้ เช่น http://localhost:8000 — ใช้ประกอบลิงก์ mock ThaiD",
    )
    mock_province: Optional[str] = Field(
        default=None,
        description=(
            "เฉพาะ mock OIDC (dev) — เลือกที่อยู่จำลองตามชื่อจังหวัดเพื่อทดสอบ province gate "
            "(TASK-v-care-12062026-01) ส่งต่อไป thaid-auth-service ตรง ๆ"
        ),
    )


@router.post(
    "/v1/notifications",
    tags=["notifications"],
    summary="สร้างการแจ้งเตือน",
    description="ส่งต่อไปยัง notification-service `POST /v1/notifications`",
    dependencies=_require_internal_api_key,
)
async def create_notification(body: CreateNotificationRequest):
    """รับคำขอแจ้งเตือนแล้วส่งต่อ POST ไป notification-service."""
    return await _post(f"{settings.notification_service_url}/v1/notifications", json=body.model_dump())


@router.get(
    "/v1/case_for_staff/status-summary",
    tags=["case_for_staff"],
    summary="สรุปจำนวนคำร้องตาม bucket สำหรับ staff digest",
    description="ส่งต่อ `GET …/v1/case_for_staff/status-summary` ใน case-service",
    response_model=CaseForStaffStatusSummaryResponse,
    dependencies=_require_internal_api_key,
)
async def get_case_for_staff_status_summary(
    province_id: int = Query(..., description="รหัสจังหวัด"),
) -> CaseForStaffStatusSummaryResponse:
    base = settings.case_service_url.rstrip("/")
    data = await _get(f"{base}/v1/case_for_staff/status-summary?province_id={province_id}")
    return CaseForStaffStatusSummaryResponse.model_validate(data)


@router.post(
    "/v1/notifications/staff-digest",
    tags=["notifications"],
    summary="ส่งอีเมลสรุปคำร้องรายวัน (staff digest)",
    description=(
        "ดึง status-summary ต่อจังหวัดจาก case-service แล้วส่งอีเมล STAFF_CASE_STATUS_DIGEST "
        "ผ่าน notification-service — แสดงเฉพาะ bucket ตาม role ของผู้รับ + คำร้องเร่งด่วน (is_emergency). "
        "ส่งอีเมลทุกครั้งที่เรียก API (ระบบต้นทางควบคุมความถี่ด้วย cron). "
        "Request body: digest_date, idempotency_bucket (optional, อ้างอิงเท่านั้น), skip_if_all_zero, recipients — "
        "ตัวอย่าง: notification-service/docs/STAFF_DIGEST.md"
    ),
    response_model=StaffDigestDispatchResult,
    dependencies=_require_internal_api_key,
)
async def post_staff_digest(body: StaffDigestRequest) -> StaffDigestDispatchResult:
    return await dispatch_staff_digest(
        case_service_url=settings.case_service_url,
        notification_service_url=settings.notification_service_url,
        frontend_url=settings.frontend_url,
        body=body,
        post_json=_post,
        get_json=_get,
    )


@router.get(
    "/v1/auth/thaid/login",
    tags=["auth"],
    summary="ThaiD login (เบราว์เซอร์เปิดตรง → 302 redirect)",
    description=(
        "สำหรับให้เบราว์เซอร์ navigate มาตรงๆ — ส่งต่อ GET ไป thaid-auth-service "
        "แล้ว proxy 302 redirect ไป ThaiD authorization URL ให้เบราว์เซอร์ follow ต่อ "
        "(ไม่ต้อง X-API-Key เพราะเบราว์เซอร์เปิดโดยตรง เหมือน callback)"
    ),
)
async def thaid_login_redirect(
    post_login_redirect: Optional[str] = None,
    browser_oauth_base: Optional[str] = None,
    mock_province: Optional[str] = None,
):
    """
    รับ query params แล้วโยงต่อ GET /v1/auth/thaid/login ของ thaid-auth-service
    ซึ่งจะ 302 → ThaiD authorization URL — BFF proxy 302 นั้นกลับให้เบราว์เซอร์ follow ต่อ
    (ไม่ follow_redirects เองเพราะจะทำให้ BFF ดึงหน้า ThaiD ฝั่ง server แทน)
    """
    from urllib.parse import urlencode

    base = settings.thaid_auth_service_url.strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=500, detail="thaid_auth_service_url_not_configured")

    params: dict[str, str] = {}
    if post_login_redirect:
        params["post_login_redirect"] = post_login_redirect
    if browser_oauth_base:
        params["browser_oauth_base"] = browser_oauth_base
    if mock_province:
        params["mock_province"] = mock_province

    url = f"{base}/v1/auth/thaid/login"
    if params:
        url = f"{url}?{urlencode(params)}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, follow_redirects=False)

    if r.status_code in (301, 302, 303, 307, 308):
        loc = r.headers.get("location")
        if not loc:
            raise HTTPException(status_code=502, detail="upstream_redirect_without_location")
        return RedirectResponse(url=loc, status_code=r.status_code)

    ct = (r.headers.get("content-type") or "").lower()
    if r.status_code >= 400:
        detail: Any = r.text
        try:
            if "application/json" in ct:
                detail = r.json()
        except ValueError:
            pass
        raise HTTPException(status_code=r.status_code, detail=detail)

    if "application/json" in ct:
        return JSONResponse(content=r.json(), status_code=r.status_code)
    return JSONResponse(content={"raw": r.text}, status_code=r.status_code)


@router.post(
    "/v1/auth/thaid/login",
    tags=["auth"],
    summary="ThaiD login",
    description="ส่งต่อไปยัง thaid-auth-service `POST /v1/auth/thaid/login`",
)
async def thaid_login(body: ThaidLoginBody = ThaidLoginBody()):
    """เริ่ม flow ThaiD login โดยส่งต่อ POST ไป thaid-auth-service (รองรับ post_login_redirect)."""
    payload = body.model_dump(exclude_none=True)
    json_body = payload if payload else {}
    return await _post_thaid_auth_login(json_body)


@router.get(
    "/v1/auth/thaid/mock/continue",
    tags=["auth"],
    summary="ThaiD mock continue (เบราว์เซอร์)",
    description="ส่งต่อไป `thaid-auth-service` — ใช้ในโหมดจำลอง OAuth (ลิงก์ต้องเปิดจากเบราว์เซอร์ ไม่ใส่ X-API-Key)",
)
async def thaid_mock_continue_proxy(request: Request):
    """รับ `state` แล้วโยงต่อ mock/continue บน auth service (ได้ 302 ไป callback)."""
    base = f"{settings.thaid_auth_service_url.rstrip('/')}/v1/auth/thaid/mock/continue"
    url = f"{base}?{request.query_params}" if request.query_params else base
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url, follow_redirects=False)
    if r.status_code in (301, 302, 303, 307, 308):
        loc = r.headers.get("location")
        if not loc:
            raise HTTPException(status_code=502, detail="upstream_redirect_without_location")
        return RedirectResponse(url=loc, status_code=r.status_code)
    ct = (r.headers.get("content-type") or "").lower()
    if r.status_code >= 400:
        detail: object = r.text
        try:
            if "application/json" in ct:
                detail = r.json()
        except ValueError:
            pass
        raise HTTPException(status_code=r.status_code, detail=detail)
    if "application/json" in ct:
        return JSONResponse(content=r.json(), status_code=r.status_code)
    if "text/html" in ct:
        return HTMLResponse(content=r.text, status_code=r.status_code)
    return JSONResponse(content={"raw": r.text}, status_code=r.status_code)


@router.get(
    "/v1/auth/thaid/callback",
    tags=["auth"],
    summary="ThaiD OAuth callback (เบราว์เซอร์)",
    description=(
        "ส่งต่อ query string จาก ThaiD ไป `thaid-auth-service` — **ไม่ใส่ X-API-Key** "
        "เพราะเป็น redirect จากเบราว์เซอร์หลังผู้ใช้ยืนยันตัวตน"
    ),
)
async def thaid_callback_proxy(request: Request):
    """รับ `code`/`state` จาก redirect ของ ThaiD แล้วโยงต่อไป auth service (JSON หรือ 302 ตาม upstream).

    กรณี ThaiD ส่ง `error` กลับมา (เช่น ผู้ใช้กดปฏิเสธ) จะ redirect ไปหน้า return ของ
    frontend ทันที โดยไม่โยงต่อ auth service เพื่อให้ frontend แสดง error message ได้ถูกต้อง
    แทนที่จะแสดง JSON error ดิบในเบราว์เซอร์
    """
    params = dict(request.query_params)

    # ThaiD ส่ง error กลับมา (เช่น error=User / access_denied / temporarily_unavailable)
    # → redirect ตรงไปหน้า return ของ frontend พร้อมส่ง error param ต่อไป
    # frontend (LoginThaIDReturnPage) จะแปลง error code เป็นข้อความไทยและพาไปหน้า login
    if "error" in params:
        from urllib.parse import urlencode
        frontend_return = settings.frontend_url.rstrip("/") + "/login/thaid/return"
        err_params: dict[str, str] = {"error": params["error"]}
        if params.get("error_description"):
            err_params["error_description"] = params["error_description"]
        return RedirectResponse(
            url=f"{frontend_return}?{urlencode(err_params)}",
            status_code=302,
        )

    base = f"{settings.thaid_auth_service_url}/v1/auth/thaid/callback"
    url = f"{base}?{request.query_params}" if request.query_params else base
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url, follow_redirects=False)
    if r.status_code in (301, 302, 303, 307, 308):
        loc = r.headers.get("location")
        if not loc:
            raise HTTPException(status_code=502, detail="upstream_redirect_without_location")
        return RedirectResponse(url=loc, status_code=r.status_code)
    ct = (r.headers.get("content-type") or "").lower()
    if r.status_code >= 400:
        # auth service คืน error — redirect กลับ frontend แทนการแสดง JSON ดิบ
        from urllib.parse import urlencode
        frontend_return = settings.frontend_url.rstrip("/") + "/login/thaid/return"
        try:
            body = r.json() if "application/json" in ct else {}
        except ValueError:
            body = {}
        err_code = body.get("detail") or "auth_error"
        if isinstance(err_code, dict):
            err_code = err_code.get("detail", "auth_error")
        return RedirectResponse(
            url=f"{frontend_return}?{urlencode({'error': str(err_code)})}",
            status_code=302,
        )
    if "application/json" in ct:
        return JSONResponse(content=r.json(), status_code=r.status_code)
    if "text/html" in ct:
        return HTMLResponse(content=r.text, status_code=r.status_code)
    return JSONResponse(content={"raw": r.text}, status_code=r.status_code)


@router.get(
    "/v1/auth/thaid/status",
    tags=["auth"],
    summary="สถานะล็อกอิน ThaID (poll หลังสแกน QR)",
    description="ส่งต่อไปยัง thaid-auth-service `GET /v1/auth/thaid/status`",
)
async def thaid_login_status(state: str):
    """ใช้คู่กับ flow QR: ฝั่งเดสก์ท็อป poll จนได้ access_token."""
    from urllib.parse import quote

    enc = quote(state, safe="")
    return await _get(f"{settings.thaid_auth_service_url}/v1/auth/thaid/status?state={enc}")


@router.get(
    "/v1/auth/thaid/mock/provinces",
    tags=["auth"],
    summary="รายชื่อจังหวัด mock สำหรับทดสอบ province gate (dev เท่านั้น)",
    description=(
        "ส่งต่อไปยัง thaid-auth-service `GET /v1/auth/thaid/mock/provinces` — "
        "404 เมื่อ thaid-auth-service ไม่ได้อยู่โหมด mock OIDC (TASK-v-care-12062026-01)"
    ),
)
async def thaid_mock_provinces():
    """รายชื่อจังหวัดที่มีที่อยู่ตัวอย่างใน mock_profile_seed.json — ใช้ทำ dropdown เลือกจังหวัดฝั่ง FE."""
    return await _get(f"{settings.thaid_auth_service_url}/v1/auth/thaid/mock/provinces")


@router.get(
    "/v1/me",
    tags=["auth"],
    summary="ข้อมูลผู้ใช้ปัจจุบัน",
    description="ส่งต่อไปยัง thaid-auth-service `GET /v1/me` พร้อม header Authorization",
)
async def me(authorization: str = Depends(require_citizen_bearer)):
    """
    ดึงโปรไฟล์ผู้ใช้จาก thaid-auth-service โดยส่ง header Authorization ต่อไปตรง ๆ
    """
    return await _get(
        f"{settings.thaid_auth_service_url}/v1/me",
        headers=_forward_auth_headers(authorization),
    )


@router.post(
    "/v1/auth/logout",
    tags=["auth"],
    summary="ออกจากระบบ",
    description="ส่งต่อไปยัง thaid-auth-service `POST /v1/auth/logout` — ลบ opaque session (ถ้ามี)",
)
async def auth_logout(authorization: str = Depends(require_citizen_bearer)) -> Any:
    return await _post(
        f"{settings.thaid_auth_service_url}/v1/auth/logout",
        json={},
        headers=_forward_auth_headers(authorization),
    )



# ─── Satisfaction survey ───────────────────────────────────────────────────────


class SatisfactionSurveyCreateBody(BaseModel):
    applicant_id: int = Field(..., ge=1)
    survey_type: str = Field(..., pattern="^(system_usage|aid_received)$")
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


@router.post(
    "/v1/satisfaction",
    tags=["satisfaction"],
    summary="บันทึกผลประเมินความพึงพอใจ",
    description=(
        "ส่งต่อ `POST …/v1/satisfaction` ใน case-service — "
        "survey_type: 'system_usage' (หลังยื่นฟอร์ม) หรือ 'aid_received' (หลังเบิกจ่าย)"
    ),
    status_code=status.HTTP_201_CREATED,
)
async def create_satisfaction_survey(
    body: SatisfactionSurveyCreateBody,
    authorization: str = Depends(require_citizen_bearer),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    return await _post(
        f"{base}/v1/satisfaction",
        json=body.model_dump(),
        headers=_forward_auth_headers(authorization),
    )


@router.get(
    "/v1/satisfaction",
    tags=["satisfaction"],
    summary="ดูผลประเมินความพึงพอใจของ applicant",
    description="ส่งต่อ `GET …/v1/satisfaction?applicant_id=…` ใน case-service",
)
async def list_satisfaction_surveys(
    applicant_id: int = Query(..., ge=1),
    authorization: str = Depends(require_citizen_bearer),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    return await _get(
        f"{base}/v1/satisfaction?applicant_id={applicant_id}",
        headers=_forward_auth_headers(authorization),
    )


# ---------------------------------------------------------------------------
# Admin (TASK-v-care-12062026-01) — เปิด/ปิดบริการรายจังหวัด
# ส่งต่อ case-service; admin JWT (Authorization) ถูก forward ไปให้ case-service ตรวจ
# ---------------------------------------------------------------------------


class AdminLoginProxyBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=255)


class AdminProvinceAccessUpdateBody(BaseModel):
    is_enabled: bool


class AdminRandomCasesCreateBody(BaseModel):
    count: int = Field(1, ge=1, le=50)
    province_id: int | None = Field(None, ge=1)


@router.post(
    "/v1/admin/auth/login",
    tags=["admin"],
    summary="Admin login → JWT",
    description="ส่งต่อ `POST …/v1/admin/auth/login` ใน case-service — คืน admin access_token",
)
async def admin_login(body: AdminLoginProxyBody) -> Dict[str, Any]:
    base = settings.case_service_url.rstrip("/")
    return await _post(f"{base}/v1/admin/auth/login", json=body.model_dump())


@router.get(
    "/v1/admin/provinces",
    tags=["admin"],
    summary="รายการจังหวัด + สถานะเปิด/ปิด",
    description="ส่งต่อ `GET …/v1/admin/provinces` ใน case-service (ต้องส่ง admin JWT ใน Authorization)",
    dependencies=_require_bearer_any,
)
async def admin_list_provinces(
    authorization: Optional[str] = Header(default=None),
) -> Any:
    base = settings.case_service_url.rstrip("/")
    return await _get(
        f"{base}/v1/admin/provinces",
        headers=_forward_auth_headers(authorization),
    )


@router.put(
    "/v1/admin/provinces/bulk",
    tags=["admin"],
    summary="เปิด/ปิดทุกจังหวัดพร้อมกัน",
    description="ส่งต่อ `PUT …/v1/admin/provinces/bulk` ใน case-service (ต้องส่ง admin JWT)",
    dependencies=_require_bearer_any,
)
async def admin_update_all_provinces(
    body: AdminProvinceAccessUpdateBody,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    base = settings.case_service_url.rstrip("/")
    return await _put(
        f"{base}/v1/admin/provinces/bulk",
        json=body.model_dump(),
        headers=_forward_auth_headers(authorization),
    )


@router.put(
    "/v1/admin/provinces/{province_id}",
    tags=["admin"],
    summary="เปิด/ปิดการบันทึกข้อมูลของจังหวัด",
    description="ส่งต่อ `PUT …/v1/admin/provinces/{province_id}` ใน case-service (ต้องส่ง admin JWT)",
    dependencies=_require_bearer_any,
)
async def admin_update_province(
    province_id: int,
    body: AdminProvinceAccessUpdateBody,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    base = settings.case_service_url.rstrip("/")
    return await _put(
        f"{base}/v1/admin/provinces/{province_id}",
        json=body.model_dump(),
        headers=_forward_auth_headers(authorization),
    )


@router.post(
    "/v1/admin/cases/random",
    tags=["admin"],
    summary="สร้างคำร้องสุ่ม (dev/staging)",
    description=(
        "ส่งต่อ `POST …/v1/admin/cases/random` ใน case-service — "
        "สร้าง person + คำร้องสุ่ม (ต้องส่ง admin JWT; ปิดบน production)"
    ),
    dependencies=_require_bearer_any,
)
async def admin_create_random_cases(
    body: AdminRandomCasesCreateBody,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    base = settings.case_service_url.rstrip("/")
    return await _post(
        f"{base}/v1/admin/cases/random",
        json=body.model_dump(exclude_none=True),
        timeout=120.0,
        headers=_forward_auth_headers(authorization),
    )


# ---------------------------------------------------------------------------
# Dashboard — ส่งต่อ dashboard-service; รับ province_id/current_status_id/type_money_id
# ตรงจาก query param เหมือน /v1/case_for_staff (ไม่มี permission/scope check ที่ BFF ตอนนี้)
# ---------------------------------------------------------------------------


def _multi_query_pairs(base: list[tuple[str, Any]], key: str, values: Optional[list[int]]) -> list[tuple[str, Any]]:
    pairs = list(base)
    if values:
        for v in values:
            pairs.append((key, v))
    return pairs


@router.get(
    "/v1/dashboard/national/overview",
    tags=["dashboard"],
    summary="สรุปจำนวนคำร้องทั้งประเทศ แยกตามสถานะ (donut chart ระดับประเทศ)",
    response_model=DashboardNationalOverviewRead,
    dependencies=_require_bearer_or_trusted_api_key,
)
async def get_dashboard_national_overview(
    type_money_id: Optional[list[int]] = Query(None),
) -> DashboardNationalOverviewRead:
    base = settings.dashboard_service_url.rstrip("/")
    pairs = _multi_query_pairs([], "type_money_id", type_money_id)
    data = await _get(f"{base}/v1/dashboard/national/overview?{urlencode(pairs)}")
    return DashboardNationalOverviewRead.model_validate(data)


@router.get(
    "/v1/dashboard/provinces",
    tags=["dashboard"],
    summary="ตารางสรุปรายจังหวัดทั้งประเทศ แยกตามสถานะ (มี pagination)",
    response_model=DashboardProvincesRead,
    dependencies=_require_bearer_or_trusted_api_key,
)
async def get_dashboard_provinces(
    current_status_id: Optional[list[int]] = Query(None),
    type_money_id: Optional[list[int]] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> DashboardProvincesRead:
    base = settings.dashboard_service_url.rstrip("/")
    pairs: list[tuple[str, Any]] = [("page", page), ("page_size", page_size)]
    pairs = _multi_query_pairs(pairs, "current_status_id", current_status_id)
    pairs = _multi_query_pairs(pairs, "type_money_id", type_money_id)
    data = await _get(f"{base}/v1/dashboard/provinces?{urlencode(pairs)}")
    return DashboardProvincesRead.model_validate(data)


@router.get(
    "/v1/dashboard/provinces/export",
    tags=["dashboard"],
    summary="ดาวน์โหลด Excel ตารางสรุปรายจังหวัดทั้งประเทศ",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def get_dashboard_provinces_export(
    current_status_id: Optional[list[int]] = Query(None),
    type_money_id: Optional[list[int]] = Query(None),
) -> Response:
    base = settings.dashboard_service_url.rstrip("/")
    pairs = _multi_query_pairs([], "current_status_id", current_status_id)
    pairs = _multi_query_pairs(pairs, "type_money_id", type_money_id)
    r = await _get_raw(f"{base}/v1/dashboard/provinces/export?{urlencode(pairs)}", timeout=60.0)
    out_headers: Dict[str, str] = {}
    if cd := r.headers.get("content-disposition"):
        out_headers["content-disposition"] = cd
    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        headers=out_headers,
    )


@router.get(
    "/v1/dashboard/overview",
    tags=["dashboard"],
    summary="สรุปจำนวนคำร้องตามสถานะของจังหวัด (สำหรับ donut chart)",
    description="ส่งต่อ `GET …/v1/dashboard/overview?province_id=…` ใน dashboard-service",
    response_model=DashboardOverviewRead,
    dependencies=_require_bearer_or_trusted_api_key,
)
async def get_dashboard_overview(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการดู"),
    type_money_id: Optional[list[int]] = Query(
        None, description="กรองตาม type_money_category.id ได้หลายค่า"
    ),
) -> DashboardOverviewRead:
    base = settings.dashboard_service_url.rstrip("/")
    pairs = _multi_query_pairs([("province_id", province_id)], "type_money_id", type_money_id)
    data = await _get(f"{base}/v1/dashboard/overview?{urlencode(pairs)}")
    return DashboardOverviewRead.model_validate(data)


@router.get(
    "/v1/dashboard/districts",
    tags=["dashboard"],
    summary="ตารางสรุปรายอำเภอ แยกตามสถานะ (มี pagination)",
    description=(
        "ส่งต่อ `GET …/v1/dashboard/districts` ใน dashboard-service — "
        "คืนทุกอำเภอในจังหวัด (แม้ count=0) พร้อม status_counts ต่อ current_status_id"
    ),
    response_model=DashboardDistrictsRead,
    dependencies=_require_bearer_or_trusted_api_key,
)
async def get_dashboard_districts(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการดู"),
    current_status_id: Optional[list[int]] = Query(
        None, description="กรองตาม current_status_id ได้หลายค่า"
    ),
    type_money_id: Optional[list[int]] = Query(
        None, description="กรองตาม type_money_category.id ได้หลายค่า"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> DashboardDistrictsRead:
    base = settings.dashboard_service_url.rstrip("/")
    pairs: list[tuple[str, Any]] = [
        ("province_id", province_id),
        ("page", page),
        ("page_size", page_size),
    ]
    pairs = _multi_query_pairs(pairs, "current_status_id", current_status_id)
    pairs = _multi_query_pairs(pairs, "type_money_id", type_money_id)
    data = await _get(f"{base}/v1/dashboard/districts?{urlencode(pairs)}")
    return DashboardDistrictsRead.model_validate(data)


@router.get(
    "/v1/dashboard/districts/export",
    tags=["dashboard"],
    summary="ดาวน์โหลด Excel ตารางสรุปรายอำเภอ",
    description="ส่งต่อ `GET …/v1/dashboard/districts/export` ใน dashboard-service — filter เดียวกับ /districts แต่ไม่มี pagination",
    dependencies=_require_bearer_or_trusted_api_key,
)
async def get_dashboard_districts_export(
    province_id: int = Query(..., description="รหัสจังหวัดที่ต้องการดู"),
    current_status_id: Optional[list[int]] = Query(None, description="กรองตาม current_status_id ได้หลายค่า"),
    type_money_id: Optional[list[int]] = Query(None, description="กรองตาม type_money_category.id ได้หลายค่า"),
) -> Response:
    base = settings.dashboard_service_url.rstrip("/")
    pairs = _multi_query_pairs([("province_id", province_id)], "current_status_id", current_status_id)
    pairs = _multi_query_pairs(pairs, "type_money_id", type_money_id)
    r = await _get_raw(f"{base}/v1/dashboard/districts/export?{urlencode(pairs)}", timeout=60.0)
    out_headers: Dict[str, str] = {}
    if cd := r.headers.get("content-disposition"):
        out_headers["content-disposition"] = cd
    return Response(
        content=r.content,
        media_type=r.headers.get(
            "content-type",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        headers=out_headers,
    )


@router.get(
    "/v1/dashboard/sub-districts",
    tags=["dashboard"],
    summary="ตารางสรุปรายตำบล แยกตามสถานะ (มี pagination)",
    description="ส่งต่อ `GET …/v1/dashboard/sub-districts` ใน dashboard-service — คืนทุกตำบลในอำเภอพร้อม status_counts",
    response_model=DashboardSubDistrictsRead,
    dependencies=_require_bearer_or_trusted_api_key,
)
async def get_dashboard_sub_districts(
    district_id: int = Query(..., description="รหัสอำเภอที่ต้องการดู"),
    province_id: int = Query(..., description="รหัสจังหวัด (ตรวจสอบว่าอำเภออยู่ในจังหวัดนี้)"),
    current_status_id: Optional[list[int]] = Query(None),
    type_money_id: Optional[list[int]] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> DashboardSubDistrictsRead:
    base = settings.dashboard_service_url.rstrip("/")
    pairs: list[tuple[str, Any]] = [
        ("district_id", district_id),
        ("province_id", province_id),
        ("page", page),
        ("page_size", page_size),
    ]
    pairs = _multi_query_pairs(pairs, "current_status_id", current_status_id)
    pairs = _multi_query_pairs(pairs, "type_money_id", type_money_id)
    data = await _get(f"{base}/v1/dashboard/sub-districts?{urlencode(pairs)}")
    return DashboardSubDistrictsRead.model_validate(data)


def _ocr_service_headers() -> Dict[str, str]:
    key = (settings.ocr_service_api_key or "").strip()
    if key:
        return {"Authorization": f"Bearer {key}"}
    return {}


@router.post(
    "/v1/ocr/bank-book",
    tags=["ocr"],
    summary="OCR สมุดบัญชี (proxy → ocr-service)",
)
async def ocr_bank_book_proxy(
    target_name: str = Form(...),
    file: UploadFile = File(...),
    applicant_id: Optional[int] = Form(None),
    authorization: str = Depends(require_citizen_bearer),
) -> Any:
    base = settings.ocr_service_url.rstrip("/")
    content = await file.read()
    data: Dict[str, str] = {"target_name": target_name}
    if applicant_id is not None:
        data["applicant_id"] = str(applicant_id)
    headers = _ocr_service_headers()
    fname = file.filename or "upload"
    ct = file.content_type or "application/octet-stream"
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{base}/v1/ocr/bank-book",
            data=data,
            files={"file": (fname, content, ct)},
            headers=headers,
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=_http_error_detail_from_response(r))
        return r.json()


@router.get(
    "/v1/ocr/results/{applicant_id}",
    tags=["ocr"],
)
async def ocr_results_proxy(
    applicant_id: int,
    limit: int = Query(10, ge=1, le=50),
    authorization: str = Depends(require_citizen_bearer),
) -> Any:
    base = settings.ocr_service_url.rstrip("/")
    headers = _ocr_service_headers()
    return await _get(f"{base}/v1/ocr/results/{applicant_id}?limit={limit}", headers=headers)


@router.patch(
    "/v1/ocr/results/{ocr_result_id}/link",
    tags=["ocr"],
)
async def ocr_link_proxy(
    ocr_result_id: int,
    body: Dict[str, Any] = Body(...),
    authorization: str = Depends(require_citizen_bearer),
) -> Any:
    base = settings.ocr_service_url.rstrip("/")
    headers = _ocr_service_headers()
    return await _patch(f"{base}/v1/ocr/results/{ocr_result_id}/link", json=body, headers=headers)


class StaffLoginProxyBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=255)


@router.post(
    "/v1/staff/auth/login",
    tags=["staff"],
    summary="Staff login → JWT",
)
async def staff_login(body: StaffLoginProxyBody) -> Dict[str, Any]:
    base = settings.case_service_url.rstrip("/")
    return await _post(f"{base}/v1/staff/auth/login", json=body.model_dump())


app.include_router(router, prefix=_api_prefix)

