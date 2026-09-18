"""ล็อกหน้าเอกสาร API (Swagger / ReDoc / openapi.json) ของ BFF.

รับการยืนยันตัวตน 2 ทาง เพื่อให้คนกับสคริปต์ใช้คนละแบบได้:

* **Cookie** — คนเปิดเบราว์เซอร์ กรอกที่หน้า login ที่ออกแบบเอง (ไม่ใช่กล่อง native)
* **HTTP Basic** — สคริปต์ QA ยิง ``curl -u "$DOCS_USERNAME:$DOCS_PASSWORD"`` ได้เหมือนเดิม

ไม่มี credential เลย → redirect ไปหน้า login (ไม่ตอบ ``WWW-Authenticate``
กล่อง native ของเบราว์เซอร์จึงไม่เด้ง) ส่วนสคริปต์ที่ส่ง Basic มาผิดจะได้ 401 ตรง ๆ

รหัสอ่านจาก ``DOCS_USERNAME`` / ``DOCS_PASSWORD`` — ล็อกทุก environment
localdev ใช้ค่าเริ่มต้น ``docs`` / ``docs`` ส่วน beta กับ production ถูกบังคับให้เปลี่ยนตั้งแต่ตอน start
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Optional
from urllib.parse import quote

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .settings import is_deployed, settings

_COOKIE_NAME = "bff_docs_session"
_SESSION_TTL_SECONDS = 8 * 60 * 60  # 8 ชั่วโมง = หนึ่งวันทำงาน

# auto_error=False เพื่อคุมเองว่าเมื่อไหร่ 401 เมื่อไหร่ redirect
_basic = HTTPBasic(auto_error=False)


class DocsLoginRequired(Exception):
    """ไม่มี credential — ให้ exception handler พาไปหน้า login."""

    def __init__(self, next_url: str) -> None:
        self.next_url = next_url


# ---------------------------------------------------------------- credentials


def _credentials_match(username: str, password: str) -> bool:
    user_ok = secrets.compare_digest(
        username.encode("utf-8"), settings.docs_username.encode("utf-8")
    )
    pass_ok = secrets.compare_digest(
        password.encode("utf-8"), settings.docs_password.encode("utf-8")
    )
    return user_ok and pass_ok


def _signing_key() -> bytes:
    """คีย์เซ็น cookie ผูกกับรหัสปัจจุบัน — เปลี่ยนรหัสแล้ว session เก่าใช้ไม่ได้ทันที."""
    raw = f"bff-docs-session:{settings.docs_username}:{settings.docs_password}"
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _issue_token() -> str:
    expires_at = int(time.time()) + _SESSION_TTL_SECONDS
    payload = str(expires_at)
    signature = hmac.new(_signing_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def _token_is_valid(token: Optional[str]) -> bool:
    if not token or "." not in token:
        return False
    payload, _, signature = token.partition(".")
    expected = hmac.new(_signing_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not secrets.compare_digest(signature, expected):
        return False
    try:
        return int(payload) > int(time.time())
    except ValueError:
        return False


# ---------------------------------------------------------------- dependency


def _login_url(prefix: str, request: Request) -> str:
    target = request.url.path
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return f"{prefix}/docs/login?next={quote(target, safe='')}"


def make_docs_guard(prefix: str):
    """สร้าง dependency ที่ใช้ร่วมกันทั้ง 3 path ของเอกสาร."""

    def require_docs_auth(
        request: Request,
        cred: Optional[HTTPBasicCredentials] = Depends(_basic),
    ) -> None:
        # สคริปต์: ส่ง Basic มาแล้วต้องได้คำตอบชัดเจน ไม่ใช่ถูก redirect ไปหน้า HTML
        if cred is not None:
            if _credentials_match(cred.username, cred.password):
                return
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid documentation credentials",
            )
        if _token_is_valid(request.cookies.get(_COOKIE_NAME)):
            return
        raise DocsLoginRequired(_login_url(prefix, request))

    return require_docs_auth


# ---------------------------------------------------------------- login page

_LOGIN_PAGE = """<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">

<style>
  /* หน้าตาแบบ Windows XP (Luna) — โทนเข้มขึ้นเล็กน้อยเพื่อความรู้สึกเขตจำกัด */
  body {{
    margin: 0; padding: 24px 16px; background: #5a7edc; color: #000000;
    font-family: Tahoma, "Sarabun", "Noto Sans Thai", Geneva, sans-serif; font-size: 13px;
    min-height: 100vh; display: flex; align-items: center; justify-content: center;
  }}
  .window {{
    width: 100%; max-width: 360px; box-sizing: border-box;
    background: #ece9d8; border: 1px solid #0831d9; padding: 3px;
    box-shadow: 3px 3px 0 rgba(0, 0, 0, .45);
  }}
  .titlebar {{
    display: flex; align-items: center; justify-content: space-between;
    height: 26px; padding: 0 3px 0 6px; margin-bottom: 8px;
    background: linear-gradient(to bottom, #0039b8 0%, #2a6fd6 8%, #0748c4 40%, #0135a8 88%, #002a90 100%);
    color: #ffffff; font-weight: bold; font-size: 12px;
    text-shadow: 1px 1px 0 rgba(0, 0, 0, .45);
  }}
  .titlebar .x {{
    width: 19px; height: 17px; line-height: 15px; text-align: center; font-size: 11px;
    background: linear-gradient(to bottom, #e9757c 0%, #d63b3b 55%, #b32020 100%);
    border: 1px solid #ffffff; color: #ffffff; font-weight: bold;
  }}
  .inner {{ padding: 14px 14px 14px; }}
  .mark {{
    display: flex; justify-content: center; margin: 4px 0 16px;
  }}
  .mark svg {{
    width: 48px; height: 48px; display: block;
    filter: drop-shadow(1px 1px 0 rgba(0, 0, 0, .25));
  }}
  fieldset {{
    border: 1px solid #ffffff; border-top-color: #aca899; border-left-color: #aca899;
    margin: 0 0 12px; padding: 10px 12px 12px;
  }}
  legend {{ font-size: 12px; font-weight: bold; padding: 0 4px; }}
  label {{ display: block; font-size: 12px; margin-bottom: 3px; }}
  input {{
    width: 100%; box-sizing: border-box; padding: 3px 4px; margin-bottom: 10px;
    font-family: Tahoma, "Sarabun", "Noto Sans Thai", sans-serif; font-size: 13px;
    color: #000000; background: #ffffff; border: 1px solid #7f9db9; border-radius: 0;
  }}
  input:focus {{ outline: 1px dotted #000000; outline-offset: 1px; }}
  .buttons {{ text-align: right; }}
  button {{
    min-width: 88px; padding: 4px 12px;
    font-family: Tahoma, "Sarabun", "Noto Sans Thai", sans-serif; font-size: 12px;
    color: #000000; border: 1px solid #003c74; border-radius: 3px; cursor: pointer;
    background: linear-gradient(to bottom, #ffffff 0%, #f1efe2 45%, #e6e3d3 46%, #d6d2c2 100%);
  }}
  button:active {{
    background: linear-gradient(to bottom, #d6d2c2 0%, #e6e3d3 54%, #f1efe2 55%, #ffffff 100%);
  }}
  .error {{
    display: flex; gap: 8px; align-items: flex-start;
    padding: 7px 9px; margin-bottom: 12px; font-size: 12px; line-height: 1.5;
    background: #ffffff; border: 1px solid #aca899;
  }}
  .error .icon {{
    flex: 0 0 auto; width: 16px; height: 16px; line-height: 16px; text-align: center;
    background: #d63b3b; color: #ffffff; font-weight: bold; border: 1px solid #8b1a1a;
  }}
</style>
</head>
<body>
  <form class="window" method="post" action="{action}">
    <div class="titlebar">
      <span>สำหรับผู้ที่ได้รับอนุญาตการเข้าถึงเอกสารเท่านั้น</span>
    </div>
    <div class="inner">
      <div class="mark" aria-hidden="true">
        <svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" role="presentation">
          <circle cx="24" cy="24" r="22" fill="#2a2f3a" stroke="#1a1e28" stroke-width="2"/>
          <circle cx="24" cy="24" r="17" fill="none" stroke="#8a909c" stroke-width="1.5"/>
          <path d="M24 10 L34 14.5 V23.5 C34 30.2 29.8 35.4 24 37.5 C18.2 35.4 14 30.2 14 23.5 V14.5 Z"
                fill="#4a5363" stroke="#c8cdd6" stroke-width="1.25" stroke-linejoin="round"/>
          <circle cx="24" cy="22" r="4.5" fill="none" stroke="#d8dde6" stroke-width="1.5"/>
          <rect x="22.6" y="25.5" width="2.8" height="6.5" rx="0.6" fill="#d8dde6"/>
        </svg>
      </div>
      {error}
      <fieldset>
        <legend>บัญชี</legend>
        <input type="hidden" name="next" value="{next_url}">
        <label for="username">ชื่อผู้ใช้</label>
        <input id="username" name="username" autocomplete="username" autofocus required>
        <label for="password">รหัสผ่าน</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required>
      </fieldset>
      <div class="buttons"><button type="submit">ตกลง</button></div>
    </div>
  </form>
</body>
</html>
"""

_ERROR_BLOCK = """<div class="error">
        <span class="icon" aria-hidden="true">!</span>
        <span>ไม่สามารถเข้าสู่ระบบได้</span>
      </div>"""


def _render_login(action: str, next_url: str, *, error: bool) -> str:
    return _LOGIN_PAGE.format(
        action=action,
        error=_ERROR_BLOCK if error else "",
        next_url=next_url,
    )


# ---------------------------------------------------------------- routes


def register_docs_routes(app: FastAPI, prefix: str) -> None:
    """ผูก route เอกสารทั้งหมด (docs / redoc / openapi.json / login / logout) เข้ากับ app."""
    guard = make_docs_guard(prefix)
    login_path = f"{prefix}/docs/login"
    docs_path = f"{prefix}/docs"

    def _safe_next(raw: Optional[str]) -> str:
        """กัน open redirect — ยอมรับเฉพาะ path ภายใน prefix ของ BFF เท่านั้น."""
        if raw and raw.startswith(f"{prefix}/") and not raw.startswith("//"):
            return raw
        return docs_path

    @app.exception_handler(DocsLoginRequired)
    async def _redirect_to_login(_: Request, exc: DocsLoginRequired) -> Response:
        return RedirectResponse(exc.next_url, status_code=status.HTTP_303_SEE_OTHER)

    @app.get(login_path, include_in_schema=False)
    def docs_login_form(request: Request, next: Optional[str] = None) -> HTMLResponse:
        if _token_is_valid(request.cookies.get(_COOKIE_NAME)):
            return RedirectResponse(_safe_next(next), status_code=status.HTTP_303_SEE_OTHER)
        return HTMLResponse(_render_login(login_path, _safe_next(next), error=False))

    @app.post(login_path, include_in_schema=False)
    def docs_login_submit(
        username: str = Form(...),
        password: str = Form(...),
        next: str = Form(default=""),
    ) -> Response:
        target = _safe_next(next)
        if not _credentials_match(username, password):
            return HTMLResponse(
                _render_login(login_path, target, error=True),
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        response = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            _COOKIE_NAME,
            _issue_token(),
            max_age=_SESSION_TTL_SECONDS,
            path=prefix,
            httponly=True,
            samesite="lax",
            # beta กับ production รันบน HTTPS — localdev บน http จึงต้องไม่ตั้ง flag นี้
            secure=is_deployed(),
        )
        return response

    @app.get(f"{prefix}/docs/logout", include_in_schema=False)
    def docs_logout() -> Response:
        response = RedirectResponse(login_path, status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(_COOKIE_NAME, path=prefix)
        return response

    @app.get(docs_path, include_in_schema=False)
    def swagger_ui_html(_: None = Depends(guard)) -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url=f"{prefix}/openapi.json",
            title=f"{app.title} — Swagger UI",
        )

    @app.get(f"{prefix}/redoc", include_in_schema=False)
    def redoc_html(_: None = Depends(guard)) -> HTMLResponse:
        return get_redoc_html(
            openapi_url=f"{prefix}/openapi.json",
            title=f"{app.title} — ReDoc",
        )

    @app.get(f"{prefix}/openapi.json", include_in_schema=False)
    def openapi_json(_: None = Depends(guard)) -> JSONResponse:
        return JSONResponse(app.openapi())
