from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hmac
from typing import Any, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from ..settings import settings

_ALGORITHM = "HS256"
_SCOPE = "ocr_api"
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer_scheme = HTTPBearer(auto_error=False)


def _require_auth_config() -> None:
    if not settings.ocr_auth_enabled:
        return
    missing: list[str] = []
    if not settings.ocr_api_key.strip():
        missing.append("ocr_api_key")
    if not settings.ocr_api_username.strip():
        missing.append("ocr_api_username")
    if not settings.ocr_api_password_hash.strip():
        missing.append("ocr_api_password_hash")
    if not settings.ocr_jwt_secret.strip():
        missing.append("ocr_jwt_secret")
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "ocr_auth_config_incomplete", "missing": missing},
        )


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw((plain or "").encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def verify_credentials(username: str, password: str) -> bool:
    _require_auth_config()
    if not settings.ocr_auth_enabled:
        return False
    username_ok = hmac.compare_digest(
        (username or "").strip(),
        settings.ocr_api_username.strip(),
    )
    password_ok = verify_password(password, settings.ocr_api_password_hash.strip())
    return username_ok and password_ok


def mint_jwt(*, subject: str) -> str:
    _require_auth_config()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.ocr_jwt_expire_minutes)
    payload = {
        "sub": subject,
        "scope": _SCOPE,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.ocr_jwt_secret, algorithm=_ALGORITHM)


def decode_jwt(token: str) -> Optional[dict[str, Any]]:
    _require_auth_config()
    if not settings.ocr_auth_enabled:
        return {"sub": "dev", "scope": _SCOPE}
    if not token:
        return None
    try:
        claims = jwt.decode(token, settings.ocr_jwt_secret, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if claims.get("scope") != _SCOPE:
        return None
    return claims


def require_api_key(x_api_key: Optional[str] = Depends(_api_key_header)) -> None:
    _require_auth_config()
    if not settings.ocr_auth_enabled:
        return
    expected = settings.ocr_api_key.strip()
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_api_key",
        )


def require_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict[str, Any]:
    _require_auth_config()
    if not settings.ocr_auth_enabled:
        return {"sub": "dev", "scope": _SCOPE}
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_bearer_token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_jwt(credentials.credentials)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid_token",
        )
    return claims


def require_integration_auth(
    _api_key: None = Depends(require_api_key),
    claims: dict[str, Any] = Depends(require_bearer_token),
) -> dict[str, Any]:
    return claims
