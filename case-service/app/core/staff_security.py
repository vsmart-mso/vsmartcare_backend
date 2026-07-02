"""Staff JWT auth + province scope (HI-01)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.admin_security import verify_password
from ..core.database import get_session
from ..models.applicant import Applicant
from ..models.geo import District, SubDistrict, SubDistrictPostcode
from ..models.person import Person
from ..settings import settings

_ALGORITHM = "HS256"


@dataclass(frozen=True)
class StaffClaims:
    staff_id: int
    username: str
    province_id: int
    display_name: str


def mint_staff_jwt(
    secret: str,
    *,
    staff_id: int,
    username: str,
    province_id: int,
    display_name: str,
    expire_minutes: int,
) -> str:
    now = int(time.time())
    payload = {
        "sub": str(staff_id),
        "username": username,
        "role": "staff",
        "province_id": province_id,
        "display_name": display_name,
        "iat": now,
        "exp": now + expire_minutes * 60,
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_staff_jwt(secret: str, token: str) -> Optional[dict[str, Any]]:
    if not secret or not token:
        return None
    try:
        claims = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if claims.get("role") != "staff":
        return None
    return claims


def _claims_from_raw(raw: dict[str, Any]) -> StaffClaims:
    province_raw = raw.get("province_id")
    sub_raw = raw.get("sub")
    if province_raw is None or sub_raw is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid_staff_token")
    return StaffClaims(
        staff_id=int(sub_raw),
        username=str(raw.get("username") or ""),
        province_id=int(province_raw),
        display_name=str(raw.get("display_name") or ""),
    )


def assert_province_scope(staff: StaffClaims, province_id: int) -> None:
    if staff.province_id != province_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="province_scope_denied")


async def assert_applicant_in_staff_province(
    session: AsyncSession,
    staff: StaffClaims,
    applicant_id: int,
) -> None:
    exists = await session.scalar(select(Applicant.id).where(Applicant.id == applicant_id))
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    province_id = await session.scalar(
        select(District.province_id)
        .join(SubDistrict, SubDistrict.district_id == District.id)
        .join(SubDistrictPostcode, SubDistrictPostcode.sub_district_id == SubDistrict.id)
        .join(Person, Person.sub_district_postcode_id == SubDistrictPostcode.id)
        .join(Applicant, Applicant.persons_id == Person.id)
        .where(Applicant.id == applicant_id)
        .limit(1)
    )
    if province_id is None:
        return
    assert_province_scope(staff, int(province_id))


async def require_staff(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> StaffClaims:
    secret = (settings.staff_jwt_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="staff_auth_not_configured",
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_bearer_token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    raw = decode_staff_jwt(secret, token)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_staff_token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    staff = _claims_from_raw(raw)

    province_param = request.query_params.get("province_id")
    if province_param is not None and str(province_param).isdigit():
        assert_province_scope(staff, int(province_param))

    applicant_param = request.path_params.get("applicant_id") or request.query_params.get(
        "applicant_id"
    )
    if applicant_param is not None and str(applicant_param).isdigit():
        await assert_applicant_in_staff_province(session, staff, int(applicant_param))

    return staff
