 """Citizen auth: decode ThaID JWT + object-level authorization (CR-01).

ใช้ secret เดียวกับ thaid-auth-service (`THAID_JWT_SECRET`) — แยกจาก admin JWT.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..models.applicant import Applicant
from ..models.person import Person
from ..settings import settings

_ALGORITHM = "HS256"


@dataclass(frozen=True)
class CitizenClaims:
    person_id: int
    pid: str
    sub: str


def normalize_cid(pid: str) -> Optional[str]:
    """รับ pid/sub จาก token — ตัดอักขระที่ไม่ใช่ตัวเลข ต้องได้ 13 หลัก."""
    p = re.sub(r"\D", "", (pid or "").strip())
    if len(p) == 13:
        return p
    return None


def decode_citizen_jwt(secret: str, token: str) -> Optional[dict[str, Any]]:
    if not secret or not token:
        return None
    try:
        return jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None


async def lookup_person_id(session: AsyncSession, pid: str) -> int:
    cid = normalize_cid(pid)
    if not cid:
        return 0
    row_id = await session.scalar(select(Person.id).where(Person.cid == cid))
    return int(row_id) if row_id is not None else 0


def assert_person_owner(persons_id: int, claims: CitizenClaims) -> None:
    if persons_id != claims.person_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found")


async def get_owned_applicant(
    session: AsyncSession,
    applicant_id: int,
    claims: CitizenClaims,
) -> Applicant:
    row = await session.get(Applicant, applicant_id)
    if row is None or row.persons_id != claims.person_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_not_found")
    return row


async def require_citizen(
    authorization: Optional[str] = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> CitizenClaims:
    secret = (settings.thaid_jwt_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="citizen_auth_not_configured",
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_bearer_token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    raw = decode_citizen_jwt(secret, token)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    pid = str(raw.get("pid") or raw.get("sub") or "").strip()
    person_id = await lookup_person_id(session, pid)
    if person_id == 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="person_not_linked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CitizenClaims(
        person_id=person_id,
        pid=pid,
        sub=str(raw.get("sub") or pid),
    )


def assert_cid_owner(cid: str, claims: CitizenClaims) -> None:
    normalized = normalize_cid(cid)
    claim_cid = normalize_cid(claims.pid)
    if not normalized or not claim_cid or normalized != claim_cid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found")
