"""ThaiD OIDC helpers: discovery, authorize URL, code exchange, userinfo."""

from __future__ import annotations

import time
from typing import Any, Dict
from urllib.parse import urlencode, urlsplit, urlunsplit

from datetime import datetime, timedelta, timezone

import httpx
import jwt

_metadata_cache: Dict[str, Any] = {}
_metadata_cache_expiry: float = 0.0
_METADATA_TTL_SEC = 3600

async def get_openid_configuration(server_metadata_url: str) -> Dict[str, Any]:
    """Fetch and cache OpenID Provider metadata."""
    global _metadata_cache, _metadata_cache_expiry
    now = time.time()
    if _metadata_cache and now < _metadata_cache_expiry:
        return _metadata_cache
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(server_metadata_url)
        r.raise_for_status()
        data = r.json()
    _metadata_cache = data
    _metadata_cache_expiry = now + _METADATA_TTL_SEC
    return data


def build_authorization_url(
    metadata: Dict[str, Any],
    *,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
) -> str:
    base = str(metadata["authorization_endpoint"])
    q = urlencode(
        {
            "response_type": "code",
            "client_id": str(client_id).strip(),
            "redirect_uri": str(redirect_uri).strip(),
            "scope": str(scope).replace(",", " ").strip(),
            "state": str(state).strip(),
        }
    )
    parts = urlsplit(base)
    sep = "&" if parts.query else "?"
    new_query = f"{parts.query}{sep}{q}" if parts.query else q
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


async def exchange_authorization_code(
    token_endpoint: str,
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"token_exchange_failed: {r.status_code} {r.text}")
        return r.json()


async def fetch_userinfo(userinfo_endpoint: str, access_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"userinfo_failed: {r.status_code} {r.text}")
        return r.json()


def normalize_profile(userinfo: Dict[str, Any]) -> Dict[str, str]:
    """Map ThaiD userinfo to stable keys for JWT and /v1/me (see THAID_FASTAPI_INTEGRATION.md)."""
    pid = userinfo.get("pid") or userinfo.get("sub")
    return {
        "pid": str(pid).strip() if pid is not None else "",
        "given_name": str(userinfo.get("given_name") or "").strip(),
        "family_name": str(userinfo.get("family_name") or "").strip(),
        "title_th": str(userinfo.get("titleTh") or userinfo.get("title") or "").strip(),
        "address": str(userinfo.get("address") or "").strip(),
        "birthdate": str(userinfo.get("birthdate") or "").strip(),
        "gender": str(userinfo.get("gender") or "").strip(),
    }


def mint_app_access_token(
    secret: str,
    *,
    profile: Dict[str, str],
    expire_minutes: int,
) -> str:
    sub = profile.get("pid") or "unknown"
    iat = datetime.now(timezone.utc)
    exp = iat + timedelta(minutes=expire_minutes)
    payload = {
        "sub": sub,
        "pid": profile.get("pid", ""),
        "given_name": profile.get("given_name", ""),
        "family_name": profile.get("family_name", ""),
        "title_th": profile.get("title_th", ""),
        "provider": "thaid",
        "iat": int(iat.timestamp()),
        "exp": int(exp.timestamp()),
        "address": profile.get("address", ""),
        "birthdate": profile.get("birthdate", ""),
        "gender": profile.get("gender", ""),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_app_access_token(secret: str, token: str) -> Dict[str, Any] | None:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def claims_from_id_token_unverified(id_token: str) -> Dict[str, Any]:
    """ใช้เฉพาะเมื่อไม่มี userinfo — ไม่ verify ลายเซ็น (ควรใช้ JWKS verify บน production)."""
    try:
        return jwt.decode(
            id_token,
            algorithms=["RS256", "ES256", "HS256"],
            options={"verify_signature": False},
        )
    except jwt.PyJWTError:
        return {}
