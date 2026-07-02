"""ThaiD OIDC helpers: discovery, authorize URL, code exchange, userinfo."""

from __future__ import annotations

import time
import re
from typing import Any, Dict, Optional, Tuple
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


def parse_dopa_formatted_address(formatted: str) -> Tuple[Optional[str], Optional[str]]:
    """
    แยกเลขที่ (adr_house_num) และหมู่ (adr_moo) จาก address.formatted ของ DOPA
    เช่น "11 หมู่ที่ 7 ต.เมืองบางขลัง อ.สวรรคโลก จ.สุโขทัย"
    """
    s = (formatted or "").strip()
    if not s:
        return None, None

    adr_moo: Optional[str] = None
    m_moo = re.search(r"หมู่ที่\s*(\d+)", s)
    if m_moo:
        adr_moo = m_moo.group(1)
        before = s[: m_moo.start()].strip()
        before = re.sub(r"^บ้านเลขที่\s*", "", before, flags=re.IGNORECASE).strip()
        adr_house = before or None
    else:
        m_house = re.match(r"^(\d+[A-Za-zก-๙\/\-]*)", s)
        adr_house = m_house.group(1).strip() if m_house else None

    if adr_house:
        adr_house = re.sub(r"^บ้านเลขที่\s*", "", adr_house, flags=re.IGNORECASE).strip() or None

    return adr_house, adr_moo


def parse_thai_address_geo(formatted: str) -> Dict[str, Optional[str]]:
    """
    แยกชื่อตำบล / อำเภอ / จังหวัด / รหัสไปรษณีย์ จาก address.formatted แบบ DOPA
    เช่น "... ต.เมืองบางขลัง อ.สวรรคโลก จ.สุโขทัย" หรือท้ายบรรทัดมีรหัส 5 หลัก
    (ใช้ตำแหน่ง ต./อ./จ. ไม่ใช้ [^อ] เพราะชื่อตำบลอาจมีตัว อ)
    """
    s = (formatted or "").strip()
    empty: Dict[str, Optional[str]] = {
        "subdistrict": None,
        "district": None,
        "province": None,
        "postcode": None,
    }
    if not s:
        return dict(empty)

    m_tambon = re.search(r"(?:ต\.|ตำบล)\s*", s)
    m_amphoe = re.search(r"\sอ\.\s*", s)
    m_prov = re.search(r"\sจ\.\s*", s)
    if not (m_tambon and m_amphoe and m_prov):
        return dict(empty)

    sub = s[m_tambon.end() : m_amphoe.start()].strip()
    dist = s[m_amphoe.end() : m_prov.start()].strip()
    tail = s[m_prov.end() :].strip()

    pc_m = re.search(r"(\d{5})\s*$", tail)
    postcode = pc_m.group(1) if pc_m else None
    prov = (tail[: pc_m.start()].strip() if pc_m else tail.strip())

    out = dict(empty)
    out["subdistrict"] = sub or None
    out["district"] = dist or None
    out["province"] = prov or None
    out["postcode"] = postcode
    return out


def _address_postcode_from_userinfo(userinfo: Dict[str, Any]) -> str:
    """ถ้า address เป็น object และมีรหัสไปรษณีย์แยกฟิลด์ — ใช้ประกอบ lookup sub_districts_postcode."""
    addr = userinfo.get("address")
    if not isinstance(addr, dict):
        return ""
    for k in ("postal_code", "postcode", "postalCode", "zip", "zipcode"):
        v = addr.get(k)
        if v is None or v == "":
            continue
        digits = re.sub(r"\D", "", str(v).strip())
        if len(digits) == 5:
            return digits
    return ""


def _address_formatted(userinfo: Dict[str, Any]) -> str:
    """DOPA ส่ง address เป็น dict ที่มีคีย์ formatted หรือสตริงเดิม."""
    addr = userinfo.get("address")
    if isinstance(addr, dict):
        return str(addr.get("formatted") or "").strip()
    return str(addr or "").strip()


_TITLE_CLAIM_KEYS = ("titleTh", "title_th", "title", "nameTitle", "prefix")


def _extract_title_th(userinfo: Dict[str, Any]) -> str:
    """ดึงคำนำหน้าจาก claim ที่ ThaiD / OIDC อาจใช้ชื่อต่างกัน."""
    for key in _TITLE_CLAIM_KEYS:
        raw = userinfo.get(key)
        if raw is None:
            continue
        s = str(raw).strip()
        if s:
            return s
    return ""


def merge_oidc_userinfo(
    id_claims: Dict[str, Any] | None,
    userinfo: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """
    รวม id_token กับ userinfo — ค่าไม่ว่างจาก userinfo ชนะ;
    ไม่ให้สตริงว่างใน userinfo ทับ title/ชื่อที่มีใน id_token แล้ว.
    """
    merged: Dict[str, Any] = dict(id_claims or {})
    for key, value in (userinfo or {}).items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        merged[key] = value
    return merged


def normalize_profile(userinfo: Dict[str, Any]) -> Dict[str, str]:
    """Map ThaiD userinfo to stable keys for JWT and /v1/me (see THAID_FASTAPI_INTEGRATION.md)."""
    pid = userinfo.get("pid") or userinfo.get("sub")
    return {
        "pid": str(pid).strip() if pid is not None else "",
        "given_name": str(userinfo.get("given_name") or "").strip(),
        "family_name": str(userinfo.get("family_name") or "").strip(),
        "title_th": _extract_title_th(userinfo),
        "address": _address_formatted(userinfo),
        "address_postcode": _address_postcode_from_userinfo(userinfo),
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
    """Legacy fallback when JWKS verify is unavailable."""
    try:
        return jwt.decode(
            id_token,
            algorithms=["RS256", "ES256", "HS256"],
            options={"verify_signature": False},
        )
    except jwt.PyJWTError:
        return {}


_jwks_cache: Dict[str, Any] = {}
_jwks_cache_expiry: float = 0.0


async def fetch_jwks(jwks_uri: str) -> Dict[str, Any]:
    global _jwks_cache, _jwks_cache_expiry
    now = time.time()
    if _jwks_cache and now < _jwks_cache_expiry:
        return _jwks_cache
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(jwks_uri)
        r.raise_for_status()
        data = r.json()
    _jwks_cache = data
    _jwks_cache_expiry = now + _METADATA_TTL_SEC
    return data


def verify_id_token(id_token: str, jwks: Dict[str, Any], *, audience: str) -> Dict[str, Any]:
    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    keys = jwks.get("keys") or []
    key_data = next((k for k in keys if k.get("kid") == kid), None)
    if key_data is None and keys:
        key_data = keys[0]
    if key_data is None:
        raise ValueError("jwks_key_not_found")
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
    return jwt.decode(
        id_token,
        public_key,
        algorithms=[header.get("alg", "RS256")],
        audience=audience,
        options={"verify_aud": bool(audience)},
    )


async def claims_from_id_token_verified(
    id_token: str,
    *,
    metadata: Dict[str, Any],
    audience: str,
) -> Dict[str, Any]:
    jwks_uri = str(metadata.get("jwks_uri") or "")
    if not jwks_uri:
        return claims_from_id_token_unverified(id_token)
    jwks = await fetch_jwks(jwks_uri)
    return verify_id_token(id_token, jwks, audience=audience)
