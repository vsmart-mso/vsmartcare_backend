from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.openapi.utils import get_openapi
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from .settings import cors_origin_list, settings

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
    {"name": "cases", "description": "การบันทึกข้อมูล case"},
    {"name": "notifications", "description": "การแจ้งเตือน"},
    {"name": "auth", "description": "Login ThaiD"},
]

app = FastAPI(
    title=settings.service_name,
    version="0.1.0",
   
    openapi_tags=_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

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
        "description": "ใส่ access token ที่ได้จาก thaid-auth-service (ปุ่ม Authorize) — ใช้กับ `/v1/me`",
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


@app.get("/", tags=["meta"], summary="สถานะ service")
def root():
    """ตอบชื่อบริการและสถานะ OK สำหรับเช็กว่า BFF ทำงานอยู่."""
    return {"service": settings.service_name, "ok": True}


@app.get("/healthz", tags=["meta"], summary="Liveness probe")
def healthz():
    """Probe ว่า process ยังมีชีวิต (ไม่ต้องพึ่ง backend อื่น) — ใช้กับ orchestrator/k8s liveness."""
    return {"ok": True}


@app.get("/readyz", tags=["meta"], summary="Readiness probe")
def readyz():
    """Probe ความพร้อมรับ traffic — ขยายให้เช็ก downstream ได้ถ้าต้องการ."""
    return {"ok": True}


async def _post(url: str, json: Dict[str, Any]) -> Dict[str, Any]:
    """ยิง HTTP POST ไปยัง URL ที่กำหนด คืน JSON; ถ้า status >= 400 จะยก HTTPException."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, json=json)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


async def _get(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """ยิง HTTP GET พร้อม header ได้เลือก คืน JSON; ถ้า status >= 400 จะยก HTTPException."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, headers=headers)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


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


class CreateCaseRequest(BaseModel):
    """โครงสร้าง body สำหรับสร้าง case ที่ส่งต่อไป case-service."""

    type: str
    title: str
    description: Optional[str] = None
    requester_user_id: Optional[str] = None
    payload: Dict[str, Any] = {}

# บันทึกข้อมูล case ที่สร้างได้ลง database
@app.post(
    "/v1/cases",
    tags=["cases"],
    summary="สร้าง case",
    description="ส่งต่อไปยัง case-service `POST /v1/cases`",
    dependencies=_v1_api_key,
)
async def create_case(body: CreateCaseRequest):
    """รับข้อมูล case จาก client แล้วส่งต่อ POST ไป case-service."""
    return await _post(f"{settings.case_service_url}/v1/cases", json=body.model_dump())

#ดึงข้อมูล case จาก database
@app.get(
    "/v1/cases/{case_id}",
    tags=["cases"],
    summary="ดึง case ตาม id",
    description="ส่งต่อไปยัง case-service `GET /v1/cases/{case_id}`",
    dependencies=_v1_api_key,
)
async def get_case(case_id: str):
    """ดึงรายละเอียด case ตาม id โดยส่งต่อ GET ไป case-service."""
    return await _get(f"{settings.case_service_url}/v1/cases/{case_id}")


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


@app.post(
    "/v1/notifications",
    tags=["notifications"],
    summary="สร้างการแจ้งเตือน",
    description="ส่งต่อไปยัง notification-service `POST /v1/notifications`",
    dependencies=_v1_api_key,
)
async def create_notification(body: CreateNotificationRequest):
    """รับคำขอแจ้งเตือนแล้วส่งต่อ POST ไป notification-service."""
    return await _post(f"{settings.notification_service_url}/v1/notifications", json=body.model_dump())


@app.post(
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


@app.get(
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


@app.get(
    "/v1/auth/thaid/callback",
    tags=["auth"],
    summary="ThaiD OAuth callback (เบราว์เซอร์)",
    description=(
        "ส่งต่อ query string จาก ThaiD ไป `thaid-auth-service` — **ไม่ใส่ X-API-Key** "
        "เพราะเป็น redirect จากเบราว์เซอร์หลังผู้ใช้ยืนยันตัวตน"
    ),
)
async def thaid_callback_proxy(request: Request):
    """รับ `code`/`state` จาก redirect ของ ThaiD แล้วโยงต่อไป auth service (JSON หรือ 302 ตาม upstream)."""
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


@app.get(
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


@app.get(
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

