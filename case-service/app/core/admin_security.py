"""ความปลอดภัยฝั่ง admin: bcrypt password + admin JWT (HS256).

แยกจาก citizen token ของ thaid-auth-service โดยสิ้นเชิง — ใช้ secret คนละตัว
(`ADMIN_JWT_SECRET`) เพื่อไม่ให้ citizen token เข้าถึง admin API ได้.

ใช้ไลบรารี `bcrypt` โดยตรง (ไม่พึ่ง passlib) — bcrypt จำกัด password ที่ 72 ไบต์
จึง truncate ก่อนเสมอเพื่อความสม่ำเสมอ.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import bcrypt
import jwt

_ALGORITHM = "HS256"
_BCRYPT_MAX_BYTES = 72


def _to_bcrypt_bytes(plain: str) -> bytes:
    """bcrypt รองรับ password สูงสุด 72 ไบต์ — ตัดส่วนเกินทิ้ง (พฤติกรรมมาตรฐาน)."""
    return (plain or "").encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_to_bcrypt_bytes(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(_to_bcrypt_bytes(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):  # hash เสีย/ฟอร์แมตผิด ถือว่าไม่ผ่าน
        return False


def mint_admin_jwt(secret: str, *, admin_id: int, username: str, expire_minutes: int) -> str:
    now = int(time.time())
    payload = {
        "sub": str(admin_id),
        "username": username,
        "role": "admin",
        "iat": now,
        "exp": now + expire_minutes * 60,
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_admin_jwt(secret: str, token: str) -> Optional[dict[str, Any]]:
    """คืน claims ถ้า valid + role=admin, ไม่งั้นคืน None."""
    if not secret or not token:
        return None
    try:
        claims = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except Exception:  # noqa: BLE001
        return None
    if claims.get("role") != "admin":
        return None
    return claims
