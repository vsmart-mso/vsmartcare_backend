from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.openapi.utils import get_openapi
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from .settings import cors_origin_list, settings
from .case_display_schema import CaseDisplayRead
from .welfare_case_schema import WelfareCaseCreate

_optional_bearer = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_bff_api_key(x_api_key: Optional[str] = Depends(_api_key_header)) -> None:
    """ถ้าตั้ง `BFF_API_PASSWORD` ใน env จะบังคับให้ client ส่ง `X-API-Key` ให้ตรงกัน."""
    expected = settings.bff_api_password
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(
            status_code=401,
            detail="ต้องส่ง header X-API-Key ให้ตรงกับรหัสที่กำหนดใน BFF_API_PASSWORD",
        )


_v1_api_key = [Depends(require_bff_api_key)]

_TAGS = [
    {"name": "meta", "description": "ข้อมูล service และ health checks"},
    {"name": "applicants", "description": "การจัดการข้อมูล applicant"},
    {"name": "cases", "description": "การบันทึกข้อมูล case"},
    {
        "name": "eligibility",
        "description": "บันทึก screening_logs / welfare_request_consents (คัดกรองเบื้องต้น ความยินยอม) ผ่าน case-service",
    },
    {"name": "lookups", "description": "ข้อมูล master / lookup จาก case-service"},
    {"name": "geo", "description": "ข้อมูลจังหวัด อำเภอ ตำบล รหัสไปรษณีย์ จาก case-service"},
    {"name": "notifications", "description": "การแจ้งเตือน"},
    {"name": "auth", "description": "Login ThaiD"},
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
        "description": f"ใส่ access token ที่ได้จาก thaid-auth-service (ปุ่ม Authorize) — ใช้กับ `{_api_prefix}/v1/me`",
    }
    components["BffApiKey"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "รหัสเข้าใช้ BFF — ตั้งค่าผ่าน env `BFF_API_PASSWORD` (ถ้าไม่ตั้ง จะไม่บังคับ)",
    }
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


async def _post(url: str, json: Dict[str, Any], *, timeout: float = 30.0) -> Dict[str, Any]:
    """ยิง HTTP POST JSON; ถ้า status >= 400 จะยก HTTPException."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=json)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


async def _post_evidence_multipart(
    url: str,
    form_fields: Dict[str, Any],
    file: UploadFile,
    *,
    timeout: float = 120.0,
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
        r = await client.post(url, data=data, files=files)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


async def _get(url: str, headers: Optional[Dict[str, str]] = None) -> Any:
    """ยิง HTTP GET พร้อม header ได้เลือก คืน JSON (object หรือ array); ถ้า status >= 400 จะยก HTTPException."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, headers=headers)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


async def _delete(url: str, *, timeout: float = 30.0) -> Any:
    """ยิง HTTP DELETE; คืน JSON ถ้ามี body และถ้า status >= 400 จะยก HTTPException."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.delete(url)
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


@router.post(
    "/v1/cases",
    tags=["cases"],
    summary="สร้างคำร้อง (บันทึก applicants และตารางย่อย)",
    description=(
        "ส่งต่อ `POST …/v1/cases` ใน case-service — บันทึก applicant, address, "
        "dependency_loads, economic_infos, welfare_request_types, welfare_histories, "
        "welfare_request_status จาก body"
    ),
    dependencies=_v1_api_key,
)
async def create_case(body: WelfareCaseCreate) -> Dict[str, Any]:
    """รับ JSON ครบแล้วส่งต่อไปบันทึกฐานข้อมูล (ยังไม่รวมรูปหลักฐาน — ใช้ `/v1/cases/{applicant_id}/evidences`)."""
    base = settings.case_service_url.rstrip("/")
    payload = body.model_dump(mode="json")
    return await _post(f"{base}/v1/cases", json=payload, timeout=120.0)


@router.post(
    "/v1/cases/{applicant_id}/evidences",
    tags=["cases"],
    summary="อัปโหลดรูปหลักฐาน (multipart)",
    description="ส่งต่อ `POST …/v1/cases/{applicant_id}/evidences` — เก็บไฟล์รูปลงจานและ welfare_evidences",
    dependencies=_v1_api_key,
)
async def upload_case_evidence(
    applicant_id: int,
    attachment_type_id: int = Form(...),
    file_other_type_name: Optional[str] = Form(None),
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    base = settings.case_service_url.rstrip("/")
    url = f"{base}/v1/cases/{applicant_id}/evidences"
    return await _post_evidence_multipart(
        url,
        {
            "attachment_type_id": attachment_type_id,
            "file_other_type_name": file_other_type_name,
        },
        file,
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
    dependencies=_v1_api_key,
)
async def list_cases_display(persons_id: int) -> list[CaseDisplayRead]:
    base = settings.case_service_url.rstrip("/")
    data = await _get(f"{base}/v1/cases/display?persons_id={persons_id}")
    return [CaseDisplayRead.model_validate(item) for item in data]


@router.get(
    "/v1/cases/{applicant_id}",
    tags=["cases"],
    summary="ดึงคำร้องตาม applicant_id",
    description="ส่งต่อ `GET …/v1/cases/{applicant_id}` (ตัวอ้างอิงคือ id จากตาราง applicants)",
    dependencies=_v1_api_key,
)
async def get_case(applicant_id: int) -> Any:
    base = settings.case_service_url.rstrip("/")
    return await _get(f"{base}/v1/cases/{applicant_id}")


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
    dependencies=_v1_api_key,
)
async def delete_applicants_by_cid(
    cid: str = Query(..., min_length=13, max_length=13, description="เลขบัตรประชาชน 13 หลัก"),
) -> ApplicantDeleteByCidResponse:
    base = settings.case_service_url.rstrip("/")
    data = await _delete(f"{base}/v1/applicants/by-cid?cid={cid}", timeout=120.0)
    return ApplicantDeleteByCidResponse.model_validate(data)


@router.get(
    "/v1/screening-logs/latest-passed",
    tags=["eligibility"],
    summary="ดึง screening log ล่าสุดที่ผ่านเกณฑ์",
    response_model=Optional[ScreeningLogReadResponse],
    dependencies=_v1_api_key,
)
async def bff_get_latest_passed_screening_log(
    person_id: int = Query(..., description="ID ของ person"),
) -> Optional[ScreeningLogReadResponse]:
    """ส่งต่อไปยัง case-service — คืน null ถ้ายังไม่เคยผ่านเกณฑ์."""
    base = settings.case_service_url.rstrip("/")
    data = await _get(f"{base}/v1/screening-logs/latest-passed?person_id={person_id}")
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
    dependencies=_v1_api_key,
)
async def bff_create_screening_log(request: Request, body: ScreeningLogCreateRequest) -> ScreeningLogReadResponse:
    """รับข้อมูลคัดกรองแล้วส่งต่อ POST ไป case-service พร้อม inject ip_address จาก request."""
    # ดึง IP จาก X-Forwarded-For (กรณีผ่าน reverse proxy) หรือ client.host
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    client_ip = forwarded or (request.client.host if request.client else None)

    payload = body.model_dump()
    payload["ip_address"] = client_ip  # override ค่าที่ frontend ส่งมา (มักเป็น null)

    data = await _post(
        f"{settings.case_service_url.rstrip('/')}/v1/screening-logs",
        json=payload,
    )
    return ScreeningLogReadResponse.model_validate(data)


@router.post(
    "/v1/welfare-request-consents",
    tags=["eligibility"],
    summary="บันทึก welfare_request_consents",
    description="ส่งต่อไปยัง case-service `POST /v1/welfare-request-consents` (ความยินยอมเบื้องต้น)",
    response_model=WelfareRequestConsentReadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=_v1_api_key,
)
async def bff_create_welfare_request_consent(
    body: WelfareRequestConsentCreateRequest,
) -> WelfareRequestConsentReadResponse:
    """รับความยินยอมแล้วส่งต่อ POST ไป case-service."""
    data = await _post(
        f"{settings.case_service_url.rstrip('/')}/v1/welfare-request-consents",
        json=body.model_dump(),
    )
    return WelfareRequestConsentReadResponse.model_validate(data)


def _case_lookup_url(path_under_v1: str) -> str:
    """path_under_v1 เช่น 'v1/lookups/prefix-types' — path parameter ต้องตรงกับ case-service ทุกตัว"""
    base = settings.case_service_url.rstrip("/")
    return f"{base}/{path_under_v1.lstrip('/')}"


# --- lookups: เส้นและชื่อพารามิเตอร์ตรงกับ case-service (ไม่ใช้ query บอกประเภท master) ---


@router.get(
    "/v1/lookups/prefix-types",
    tags=["lookups"],
    summary="รายการคำนำหน้าชื่อ",
    description="ส่งต่อ `GET .../v1/lookups/prefix-types`",
    dependencies=_v1_api_key,
)
async def bff_list_prefix_types():
    return await _get(_case_lookup_url("v1/lookups/prefix-types"))


@router.get(
    "/v1/lookups/prefix-types/{prefix_type_id}",
    tags=["lookups"],
    summary="ดึงคำนำหน้าชื่อตาม id",
    description="ส่งต่อ `GET .../v1/lookups/prefix-types/{prefix_type_id}`",
    dependencies=_v1_api_key,
)
async def bff_get_prefix_type(prefix_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/prefix-types/{prefix_type_id}"))


@router.get(
    "/v1/lookups/received-welfare-types",
    tags=["lookups"],
    summary="ประเภทสวัสดิการที่เคยได้รับ",
    description="ส่งต่อ `GET .../v1/lookups/received-welfare-types`",
    dependencies=_v1_api_key,
)
async def bff_list_received_welfare_types():
    return await _get(_case_lookup_url("v1/lookups/received-welfare-types"))


@router.get(
    "/v1/lookups/received-welfare-types/{received_welfare_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทสวัสดิการที่เคยได้รับตาม id",
    dependencies=_v1_api_key,
)
async def bff_get_received_welfare_type(received_welfare_type_id: int):
    return await _get(
        _case_lookup_url(f"v1/lookups/received-welfare-types/{received_welfare_type_id}")
    )


@router.get(
    "/v1/lookups/attachment-types",
    tags=["lookups"],
    summary="ประเภทรูปภาพ / เอกสารแนบ",
    dependencies=_v1_api_key,
)
async def bff_list_attachment_types():
    return await _get(_case_lookup_url("v1/lookups/attachment-types"))


@router.get(
    "/v1/lookups/attachment-types/{attachment_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทเอกสารแนบตาม id",
    dependencies=_v1_api_key,
)
async def bff_get_attachment_type(attachment_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/attachment-types/{attachment_type_id}"))


@router.get(
    "/v1/lookups/attachment_types",
    tags=["lookups"],
    summary="ประเภทรูปภาพ / เอกสารแนบ (alias ชื่อตาราง)",
    dependencies=_v1_api_key,
)
async def bff_list_attachment_types_snake():
    return await _get(_case_lookup_url("v1/lookups/attachment_types"))


@router.get(
    "/v1/lookups/attachment_types/{attachment_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทเอกสารแนบตาม id (alias ชื่อตาราง)",
    dependencies=_v1_api_key,
)
async def bff_get_attachment_type_snake(attachment_type_id: int):
    return await _get(
        _case_lookup_url(f"v1/lookups/attachment_types/{attachment_type_id}")
    )


@router.get(
    "/v1/lookups/current-status",
    tags=["lookups"],
    summary="สถานะคำร้อง",
    dependencies=_v1_api_key,
)
async def bff_list_current_status():
    return await _get(_case_lookup_url("v1/lookups/current-status"))


@router.get(
    "/v1/lookups/current-status/{current_status_id}",
    tags=["lookups"],
    summary="ดึงสถานะคำร้องตาม id",
    dependencies=_v1_api_key,
)
async def bff_get_current_status(current_status_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/current-status/{current_status_id}"))


@router.get(
    "/v1/lookups/request-types",
    tags=["lookups"],
    summary="ประเภทความช่วยเหลือ / คำร้อง",
    dependencies=_v1_api_key,
)
async def bff_list_request_types():
    return await _get(_case_lookup_url("v1/lookups/request-types"))


@router.get(
    "/v1/lookups/request-types/{request_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทคำร้องตาม id",
    dependencies=_v1_api_key,
)
async def bff_get_request_type(request_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/request-types/{request_type_id}"))


@router.get(
    "/v1/lookups/marital-status-types",
    tags=["lookups"],
    summary="สถานภาพสมรส",
    dependencies=_v1_api_key,
)
async def bff_list_marital_status_types():
    return await _get(_case_lookup_url("v1/lookups/marital-status-types"))


@router.get(
    "/v1/lookups/marital-status-types/{marital_status_type_id}",
    tags=["lookups"],
    summary="ดึงสถานภาพสมรสตาม id",
    dependencies=_v1_api_key,
)
async def bff_get_marital_status_type(marital_status_type_id: int):
    return await _get(
        _case_lookup_url(f"v1/lookups/marital-status-types/{marital_status_type_id}")
    )


@router.get(
    "/v1/lookups/housing-types",
    tags=["lookups"],
    summary="สภาพที่อยู่อาศัย",
    dependencies=_v1_api_key,
)
async def bff_list_housing_types():
    return await _get(_case_lookup_url("v1/lookups/housing-types"))


@router.get(
    "/v1/lookups/housing-types/{housing_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทที่อยู่อาศัยตาม id",
    dependencies=_v1_api_key,
)
async def bff_get_housing_type(housing_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/housing-types/{housing_type_id}"))


@router.get(
    "/v1/lookups/income-source-types",
    tags=["lookups"],
    summary="ประเภทของรายได้",
    dependencies=_v1_api_key,
)
async def bff_list_income_source_types():
    return await _get(_case_lookup_url("v1/lookups/income-source-types"))


@router.get(
    "/v1/lookups/income-source-types/{income_source_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทแหล่งรายได้ตาม id",
    dependencies=_v1_api_key,
)
async def bff_get_income_source_type(income_source_type_id: int):
    return await _get(
        _case_lookup_url(f"v1/lookups/income-source-types/{income_source_type_id}")
    )


@router.get(
    "/v1/lookups/dependency-types",
    tags=["lookups"],
    summary="ประเภทผู้อุปการะ",
    dependencies=_v1_api_key,
)
async def bff_list_dependency_types():
    return await _get(_case_lookup_url("v1/lookups/dependency-types"))


@router.get(
    "/v1/lookups/dependency-types/{dependency_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทผู้อุปการะตาม id",
    dependencies=_v1_api_key,
)
async def bff_get_dependency_type(dependency_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/dependency-types/{dependency_type_id}"))


@router.get(
    "/v1/lookups/address-types",
    tags=["lookups"],
    summary="ประเภทที่อยู่",
    dependencies=_v1_api_key,
)
async def bff_list_address_types():
    return await _get(_case_lookup_url("v1/lookups/address-types"))


@router.get(
    "/v1/lookups/address-types/{address_type_id}",
    tags=["lookups"],
    summary="ดึงประเภทที่อยู่ตาม id",
    dependencies=_v1_api_key,
)
async def bff_get_address_type(address_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/address-types/{address_type_id}"))


@router.get("/v1/lookups/requester-relation-types", 
    tags=["lookups"], 
    summary="ประเภทความสัมพันธ์ผู้ร้องขอ", 
    description="ส่งต่อไปยัง case-service `GET /v1/lookups/requester-relation-types`",
    dependencies=_v1_api_key,
)
async def bff_list_requester_relation_types():
    return await _get(_case_lookup_url("v1/lookups/requester-relation-types"))


@router.get("/v1/lookups/requester-relation-types/{requester-relation_type_id}", 
    tags=["lookups"], 
    summary="ดึงประเภทความสัมพันธ์ผู้ร้องขอตาม id", 
    description="ส่งต่อไปยัง case-service `GET /v1/lookups/requester-relation-types/{requester-relation_type_id}`",
    dependencies=_v1_api_key,
)
async def bff_get_requester_relation_type(requester_relation_type_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/requester-relation-types/{requester_relation_type_id}"))

@router.get(
    "/v1/lookups/bank-names",
    tags=["lookups"],
    summary="รายการชื่อธนาคาร",
    dependencies=_v1_api_key,
)
async def bff_list_bank_names():
    return await _get(_case_lookup_url("v1/lookups/bank-names"))


@router.get(
    "/v1/lookups/bank-names/{bank_name_id}",
    tags=["lookups"],
    summary="ดึงชื่อธนาคารตาม id",
    dependencies=_v1_api_key,
)
async def bff_get_bank_name(bank_name_id: int):
    return await _get(_case_lookup_url(f"v1/lookups/bank-names/{bank_name_id}"))


@router.get(
    "/v1/geo/provinces",
    tags=["geo"],
    summary="รายการจังหวัด",
    dependencies=_v1_api_key,
)
async def bff_list_provinces():
    return await _get(_case_lookup_url("v1/geo/provinces"))


@router.get(
    "/v1/geo/provinces/{province_id}",
    tags=["geo"],
    summary="ดึงจังหวัดตาม id",
    dependencies=_v1_api_key,
)
async def bff_get_province(province_id: int):
    return await _get(_case_lookup_url(f"v1/geo/provinces/{province_id}"))


@router.get(
    "/v1/geo/districts",
    tags=["geo"],
    summary="รายการอำเภอในจังหวัด",
    description="ต้องส่ง query `province_id` — ส่งต่อไป case-service",
    dependencies=_v1_api_key,
)
async def bff_list_districts(province_id: int = Query(..., description="รหัสจังหวัด")):
    return await _get(_case_lookup_url(f"v1/geo/districts?province_id={province_id}"))


@router.get(
    "/v1/geo/sub-districts",
    tags=["geo"],
    summary="รายการตำบลในอำเภอ พร้อมรหัสไปรษณีย์และแถว sub_districts_postcode",
    description="ต้องส่ง query `district_id` — response มี `sub_districts_postcode` (id bridge) สำหรับบันทึกที่อยู่",
    dependencies=_v1_api_key,
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


@router.post(
    "/v1/notifications",
    tags=["notifications"],
    summary="สร้างการแจ้งเตือน",
    description="ส่งต่อไปยัง notification-service `POST /v1/notifications`",
    dependencies=_v1_api_key,
)
async def create_notification(body: CreateNotificationRequest):
    """รับคำขอแจ้งเตือนแล้วส่งต่อ POST ไป notification-service."""
    return await _post(f"{settings.notification_service_url}/v1/notifications", json=body.model_dump())


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
    dependencies=_v1_api_key,
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
    dependencies=_v1_api_key,
)
async def thaid_login_status(state: str):
    """ใช้คู่กับ flow QR: ฝั่งเดสก์ท็อป poll จนได้ access_token."""
    from urllib.parse import quote

    enc = quote(state, safe="")
    return await _get(f"{settings.thaid_auth_service_url}/v1/auth/thaid/status?state={enc}")


@router.get(
    "/v1/me",
    tags=["auth"],
    summary="ข้อมูลผู้ใช้ปัจจุบัน",
    description="ส่งต่อไปยัง thaid-auth-service `GET /v1/me` พร้อม header Authorization",
    dependencies=_v1_api_key,
)
async def me(authorization: Optional[str] = Header(default=None)):
    """
    ดึงโปรไฟล์ผู้ใช้จาก thaid-auth-service โดยส่ง header Authorization ต่อไปตรง ๆ
    (ใช้ Header raw แทน HTTPBearer เพื่อหลีกเลี่ยงเคส parser ไม่จับ header บางรูปแบบ).
    """
    headers: Dict[str, str] = {}
    if authorization and authorization.strip():
        headers["Authorization"] = authorization.strip()
    return await _get(f"{settings.thaid_auth_service_url}/v1/me", headers=headers)


app.include_router(router, prefix=_api_prefix)

