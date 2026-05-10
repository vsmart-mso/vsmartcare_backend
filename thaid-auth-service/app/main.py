from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Literal, Optional, Union
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from . import ThaID
from . import db
from .db import configure_database, shutdown_database
from .person_persist import persist_new_person_if_absent
from .settings import cors_origin_list, settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    configure_database(settings.database_url)
    if not db.is_database_configured():
        logger.warning(
            "DATABASE_URL is empty — login will succeed but no row will be written to table `persons`. "
            "Set DATABASE_URL (e.g. postgresql+asyncpg://postgres:postgres@localhost:5436/case_service from host)."
        )
    else:
        logger.info("DATABASE_URL configured — new logins will insert into `persons` when cid is new.")
    yield
    await shutdown_database()


app = FastAPI(title=settings.service_name, version="0.1.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _use_mock_oidc() -> bool:
    return bool(settings.thaid_use_mock) or not settings.thaid_server_metadata_url.strip()


MOCK_OAUTH_CODE = "mock-dev-authorization-code"


def _browser_public_base(request: Request) -> str:
    """URL ฐานที่เบราว์เซอร์เปิด thaid-auth-service (ลิงก์ mock/callback อยู่ที่ service นี้ ไม่ใช่ BFF)."""
    raw = settings.thaid_public_base_url.strip().rstrip("/")
    if raw:
        return raw
    return str(request.base_url).rstrip("/")


def _mock_continue_url(request: Request, state: str) -> str:
    rec = _states.get(state) or {}
    bo = rec.get("browser_oauth_base")
    if isinstance(bo, str) and bo.strip():
        base = bo.strip().rstrip("/")
    elif settings.thaid_public_base_url.strip():
        base = settings.thaid_public_base_url.strip().rstrip("/")
    else:
        base = _browser_public_base(request)
    return f"{base}/v1/auth/thaid/mock/continue?state={quote(state, safe='')}"


@app.get("/")
def root():
    return {
        "service": settings.service_name,
        "ok": True,
        "mock_thaid": _use_mock_oidc(),
        "oidc_mode": "mock" if _use_mock_oidc() else "thaid",
        "persons_persist_enabled": db.is_database_configured(),
        "persons_table_name": "persons",
    }


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/readyz")
def readyz():
    return {"ok": True}


class LoginStartBody(BaseModel):
    """ตัวเลือกสำหรับฝั่งหน้า: redirect หลังล็อกอินสำเร็จ (override env ชั่วคราวต่อ state)."""

    post_login_redirect: Optional[str] = Field(
        default=None,
        description="ถ้ามี หลัง callback สำเร็จจะ 302 ไป URL นี้พร้อม query access_token (ใช้ HTTPS บน production)",
    )
    browser_oauth_base: Optional[str] = Field(
        default=None,
        description=(
            "ฐาน URL ที่เบราว์เซอร์เรียกได้สำหรับเส้นทาง OAuth เช่น http://localhost:8000 (BFF) "
            "— ใช้ประกอบลิงก์ mock/continue แทน hostname ภายใน Docker (thaid-auth-service)"
        ),
    )


class MockProfilePreview(BaseModel):
    """โปรไฟล์จำลอง (ฟิลด์เดียวกับ UserProfile / userinfo ThaiD) — แสดงในหน้า dev เท่านั้น"""

    pid: str = ""
    given_name: str = ""
    family_name: str = ""
    title_th: str = ""


class LoginStartResponse(BaseModel):
    authorization_url: str
    state: str
    flow: Literal["thaid", "dev_mock"] = "thaid"
    mock_profile: Optional[MockProfilePreview] = Field(
        default=None,
        description="มีเมื่อ flow=dev_mock — ข้อมูลเดียวกับที่จะได้หลัง callback สำเร็จ",
    )


# state -> {"created_at": datetime, "post_login_redirect": str | None}
_states: Dict[str, Dict[str, Any]] = {}
# หลัง callback สำเร็จ: state -> payload (ให้ฝั่งเดสก์ท็อป poll รับ token — flow สแกน QR)
_login_completions: Dict[str, Dict[str, Any]] = {}
_COMPLETION_TTL = timedelta(minutes=15)
# opaque access token -> profile + metadata
_sessions: Dict[str, Dict[str, str]] = {}


def _register_state(
    post_login_redirect: Optional[str],
    browser_oauth_base: Optional[str] = None,
) -> str:
    state = str(uuid4())
    _states[state] = {
        "created_at": datetime.utcnow(),
        "post_login_redirect": (post_login_redirect or "").strip() or None,
        "browser_oauth_base": (browser_oauth_base or "").strip() or None,
    }
    return state


def _consume_state(state: str) -> Dict[str, Any]:
    rec = _states.pop(state, None)
    if not rec:
        raise HTTPException(status_code=400, detail="invalid_state")
    created_at: datetime = rec["created_at"]
    if datetime.utcnow() - created_at > timedelta(minutes=10):
        raise HTTPException(status_code=400, detail="state_expired")
    return rec


def _mock_user_profile() -> Dict[str, str]:
    """ค่าเดียวกับ normalize_profile จาก userinfo จริง (รวมฟิลด์สำหรับบันทึก persons)"""
    return {
        "pid": settings.thaid_mock_pid,
        "given_name": settings.thaid_mock_given_name,
        "family_name": settings.thaid_mock_family_name,
        "title_th": settings.thaid_mock_title_th,
        "birthdate": settings.thaid_mock_birthdate,
        "gender": "",
        "address": "",
        "address_postcode": "",
    }


def _mock_profile_preview() -> MockProfilePreview:
    p = _mock_user_profile()
    return MockProfilePreview(
        pid=p.get("pid", ""),
        given_name=p.get("given_name", ""),
        family_name=p.get("family_name", ""),
        title_th=p.get("title_th", ""),
    )


@app.get("/v1/auth/thaid/mock/continue")
def mock_thaid_continue(request: Request, state: str):
    """
    ขั้นตอนจำลอง ThaiD: redirect ไป callback พร้อม code หลอก (ใช้เมื่อ mock เท่านั้น).
    """
    if not _use_mock_oidc():
        raise HTTPException(status_code=404, detail="mock_only")
    if not state.strip() or state not in _states:
        raise HTTPException(status_code=400, detail="invalid_or_expired_state")
    # ใช้ THAID_REDIRECT_URI ที่ลงทะเบียน/ตั้งค่า (มักชี้ BFF) — ห้ามใช้ request.base_url ของ container
    cb = (settings.thaid_redirect_uri or "").strip()
    if not cb:
        loc = (
            f"{_browser_public_base(request)}/v1/auth/thaid/callback?"
            f"state={quote(state, safe='')}&code={quote(MOCK_OAUTH_CODE, safe='')}"
        )
    elif "?" in cb:
        loc = f"{cb}&state={quote(state, safe='')}&code={quote(MOCK_OAUTH_CODE, safe='')}"
    else:
        loc = f"{cb}?state={quote(state, safe='')}&code={quote(MOCK_OAUTH_CODE, safe='')}"
    return RedirectResponse(url=loc, status_code=302)


@app.post("/v1/auth/thaid/login", response_model=LoginStartResponse)
async def start_login_post(request: Request, body: LoginStartBody = LoginStartBody()):
    """
    เริ่ม OAuth ThaiD: คืน `authorization_url` + `state` ให้หน้าเว็บเปิด/redirect ต่อ
    (รูปแบบ SPA / mobile in-app browser).
    """
    state = _register_state(body.post_login_redirect, body.browser_oauth_base)
    if _use_mock_oidc():
        authorization_url = _mock_continue_url(request, state)
        return LoginStartResponse(
            authorization_url=authorization_url,
            state=state,
            flow="dev_mock",
            mock_profile=_mock_profile_preview(),
        )

    if not settings.thaid_client_secret.strip():
        raise HTTPException(status_code=500, detail="thaid_client_secret_required_for_real_oidc")

    metadata = await ThaID.get_openid_configuration(settings.thaid_server_metadata_url)
    authorization_url = ThaID.build_authorization_url(
        metadata,
        client_id=settings.thaid_client_id,
        redirect_uri=settings.thaid_redirect_uri,
        scope=settings.thaid_scope,
        state=state,
    )

    return LoginStartResponse(
        authorization_url=authorization_url,
        state=state,
        flow="thaid",
    )


@app.get("/v1/auth/thaid/login")
async def start_login_get(
    request: Request,
    post_login_redirect: Optional[str] = None,
    browser_oauth_base: Optional[str] = None,
):
    """
    เบราว์เซอร์กดลิงก์ตรง: redirect 302 ไปหน้า authorize ของ ThaiD ทันที
    (ค่า post_login_redirect ใช้เหมือนใน POST body).
    """
    body = LoginStartBody(
        post_login_redirect=post_login_redirect,
        browser_oauth_base=browser_oauth_base,
    )
    out = await start_login_post(request, body)
    return RedirectResponse(url=out.authorization_url, status_code=302)


class UserProfile(BaseModel):
    pid: str = ""
    given_name: str = ""
    family_name: str = ""
    title_th: str = ""
    address: str = ""
    birthdate: str = ""
    gender: str = ""



class CallbackResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserProfile = Field(default_factory=UserProfile)


def _peek_state(state: str) -> Dict[str, Any]:
    """อ่าน state โดยไม่ pop — ใช้ตอนเริ่ม callback ก่อนแลก code (ลดช่องว่าง race กับ poll)."""
    rec = _states.get(state)
    if not rec:
        raise HTTPException(status_code=400, detail="invalid_state")
    created_at: datetime = rec["created_at"]
    if datetime.utcnow() - created_at > timedelta(minutes=10):
        _states.pop(state, None)
        raise HTTPException(status_code=400, detail="state_expired")
    return rec


def _purge_stale_completions() -> None:
    now = datetime.utcnow()
    stale = [s for s, v in _login_completions.items() if now - v["stored_at"] > _COMPLETION_TTL]
    for s in stale:
        _login_completions.pop(s, None)


def _store_login_completion(state: str, payload: CallbackResponse) -> None:
    _login_completions[state] = {
        "stored_at": datetime.utcnow(),
        "access_token": payload.access_token,
        "token_type": payload.token_type,
        "expires_in": payload.expires_in,
        "user": payload.user.model_dump(),
    }


class LoginStatusResponse(BaseModel):
    status: Literal["pending", "complete", "gone"]
    access_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    user: Optional[UserProfile] = None


@app.get("/v1/auth/thaid/status", response_model=LoginStatusResponse)
def login_status(state: str):
    """
    สำหรับเดสก์ท็อปแสดง QR: poll จนกว่า `complete` แล้วอ่าน access_token (ครั้งเดียวแล้วลบออกจาก memory).
    """
    if not state.strip():
        raise HTTPException(status_code=400, detail="missing_state")
    _purge_stale_completions()
    done = _login_completions.pop(state, None)
    if done:
        return LoginStatusResponse(
            status="complete",
            access_token=str(done["access_token"]),
            token_type=str(done["token_type"]),
            expires_in=int(done["expires_in"]),
            user=UserProfile(**done["user"]),
        )
    if state in _states:
        return LoginStatusResponse(status="pending")
    return LoginStatusResponse(status="gone")


async def _persist_person_safe(profile: Dict[str, str]) -> None:
    """บันทึก persons ถ้าตั้ง DATABASE_URL — ล้มเหลวไม่ทำให้ล็อกอินล้ม"""
    try:
        await persist_new_person_if_absent(profile)
    except Exception:  # noqa: BLE001
        logger.exception("person_persist_failed_after_login")


def _issue_access_and_store_session(profile: Dict[str, str]) -> CallbackResponse:
    expires_in = settings.thaid_jwt_expire_minutes * 60
    if settings.thaid_jwt_secret.strip():
        token = ThaID.mint_app_access_token(
            settings.thaid_jwt_secret,
            profile=profile,
            expire_minutes=settings.thaid_jwt_expire_minutes,
        )
    else:
        token = str(uuid4())
        _sessions[token] = {
            "user_id": profile.get("pid") or "unknown",
            "provider": "thaid",
            "pid": profile.get("pid", ""),
            "given_name": profile.get("given_name", ""),
            "family_name": profile.get("family_name", ""),
            "title_th": profile.get("title_th", ""),
            "address": profile.get("address", ""),
            "birthdate": profile.get("birthdate", ""),
            "gender": profile.get("gender", ""),
        }
    return CallbackResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserProfile(
            pid=profile.get("pid", ""),
            given_name=profile.get("given_name", ""),
            family_name=profile.get("family_name", ""),
            title_th=profile.get("title_th", ""),
            address=profile.get("address", ""),
            birthdate=profile.get("birthdate", ""),
            gender=profile.get("gender", ""),
        ),
    )


_THAID_CALLBACK_OK_HTML = """<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>ThaID — สำเร็จ</title>
</head>
<body style="font-family:system-ui,sans-serif;padding:2rem;max-width:28rem;margin:auto;background:#f8fafc;color:#0f172a;line-height:1.6;">
  <p style="font-size:1.125rem;font-weight:600;">ยืนยันตัวตนสำเร็จ</p>
  <p>คุณสามารถปิดหน้านี้ได้ จากนั้นกลับไปที่หน้าจอที่แสดง QR code เพื่อใช้งานระบบต่อ</p>
</body>
</html>"""


def _respond_after_thaid_login(state_rec: Dict[str, Any], payload: CallbackResponse) -> Union[RedirectResponse, HTMLResponse]:
    """คืน HTML บนมือถือหลังยืนยัน หรือ 302 ถ้ามี post_login_redirect (ผลสำหรับ poll เก็บไว้ก่อนแล้ว)."""
    target = (state_rec.get("post_login_redirect") or settings.thaid_post_login_redirect or "").strip()
    if not target:
        return HTMLResponse(content=_THAID_CALLBACK_OK_HTML, media_type="text/html; charset=utf-8")
    from urllib.parse import urlencode, urlparse, urlunparse

    q = urlencode(
        {
            "access_token": payload.access_token,
            "token_type": payload.token_type,
            "expires_in": str(payload.expires_in),
        }
    )
    parts = urlparse(target)
    sep = "&" if parts.query else "?"
    new_query = f"{parts.query}{sep}{q}" if parts.query else q
    loc = urlunparse(
        (parts.scheme, parts.netloc, parts.path, parts.params, new_query, parts.fragment)
    )
    return RedirectResponse(url=loc, status_code=302)


@app.get("/v1/auth/thaid/callback", response_model=None)
async def callback(request: Request, state: str, code: Optional[str] = None) -> Union[RedirectResponse, HTMLResponse]:
    """
    Callback จาก ThaiD: ตรวจ disapproved / code / state แล้วแลก token + userinfo
    (สอดคล้อง THAID_FASTAPI_INTEGRATION.md).
    """
    raw_query = request.url.query.lower()
    if (not code) or ("disapproved" in raw_query):
        raise HTTPException(status_code=400, detail="login_disapproved_or_missing_code")

    state_rec = _peek_state(state)
    
    # ถ้าใช้ mock oidc จะสร้าง access token และ store session
    if _use_mock_oidc():
        mock_profile = _mock_user_profile()
        payload = _issue_access_and_store_session(mock_profile)
        await _persist_person_safe(mock_profile)
        _store_login_completion(state, payload)
        _consume_state(state)
        return _respond_after_thaid_login(state_rec, payload)

    if not settings.thaid_client_secret.strip():
        raise HTTPException(status_code=500, detail="thaid_client_secret_required_for_real_oidc")

    try:
        metadata = await ThaID.get_openid_configuration(settings.thaid_server_metadata_url)
        token_ep = str(metadata["token_endpoint"])
        userinfo_ep = str(metadata.get("userinfo_endpoint") or "")
        tokens = await ThaID.exchange_authorization_code(
            token_ep,
            client_id=settings.thaid_client_id,
            client_secret=settings.thaid_client_secret,
            redirect_uri=settings.thaid_redirect_uri,
            code=code,
        )
        access = str(tokens.get("access_token") or "")
        if not access:
            raise HTTPException(status_code=502, detail="token_response_missing_access_token")
        if userinfo_ep:
            raw_userinfo = await ThaID.fetch_userinfo(userinfo_ep, access)
        else:
            raw_userinfo = {}
        id_tok = tokens.get("id_token")
        if isinstance(id_tok, str) and id_tok.strip():
            merged = {**ThaID.claims_from_id_token_unverified(id_tok), **raw_userinfo}
            raw_userinfo = merged
        profile = ThaID.normalize_profile(raw_userinfo)
        if not profile.get("pid"):
            raise HTTPException(status_code=400, detail="missing_pid_in_userinfo")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("thaid_callback_failed: %s", exc)
        raise HTTPException(status_code=502, detail="thaid_token_or_userinfo_failed") from exc
    await _persist_person_safe(profile)
    # สร้าง access token และ store session
    payload = _issue_access_and_store_session(profile)
    # บันทึกสถานะการ login ไว้ใน memory
    _store_login_completion(state, payload)
    # ลบ state ออกจาก memory กรณีใช้ login สำเร็จเเล้วในรอบนั้น 
    _consume_state(state)
    return _respond_after_thaid_login(state_rec, payload)


class MeResponse(BaseModel):
    user_id: str
    provider: str
    pid: str = ""
    given_name: str = ""
    family_name: str = ""
    title_th: str = ""


@app.get("/v1/me", response_model=MeResponse)
def me(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    token = authorization.split(" ", 1)[1].strip()

    if settings.thaid_jwt_secret.strip():
        claims = ThaID.decode_app_access_token(settings.thaid_jwt_secret, token)
        if not claims:
            raise HTTPException(status_code=401, detail="invalid_token")
        return MeResponse(
            user_id=str(claims.get("sub") or claims.get("pid") or ""),
            provider=str(claims.get("provider") or "thaid"),
            pid=str(claims.get("pid") or ""),
            given_name=str(claims.get("given_name") or ""),
            family_name=str(claims.get("family_name") or ""),
            title_th=str(claims.get("title_th") or ""),
        )

    s = _sessions.get(token)
    if not s:
        raise HTTPException(status_code=401, detail="invalid_token")
    return MeResponse(
        user_id=s.get("user_id", ""),
        provider=s.get("provider", "thaid"),
        pid=s.get("pid", ""),
        given_name=s.get("given_name", ""),
        family_name=s.get("family_name", ""),
        title_th=s.get("title_th", ""),
    )
