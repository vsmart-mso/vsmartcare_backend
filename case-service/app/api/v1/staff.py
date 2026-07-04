"""Staff auth API (HI-01)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.admin_security import hash_password, verify_password
from ...core.staff_security import mint_staff_jwt
from ...core.database import get_session
from ...models.staff import StaffUser
from ...schemas.staff import StaffLoginBody, StaffTokenResponse
from ...settings import settings

router = APIRouter(prefix="/v1/staff", tags=["staff"])

_DUMMY_PASSWORD_HASH = hash_password("timing-equalizer-not-a-real-password")


@router.post("/auth/login", response_model=StaffTokenResponse)
async def staff_login(
    body: StaffLoginBody,
    session: AsyncSession = Depends(get_session),
) -> StaffTokenResponse:
    if not settings.staff_jwt_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="staff_jwt_secret_not_configured",
        )

    staff = await session.scalar(
        select(StaffUser).where(StaffUser.username == body.username.strip())
    )
    hashed = staff.password_hash if staff is not None else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(body.password, hashed)
    if staff is None or not staff.is_active or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials"
        )

    expire_minutes = settings.staff_jwt_expire_minutes
    token = mint_staff_jwt(
        settings.staff_jwt_secret,
        staff_id=staff.id,
        username=staff.username,
        province_id=staff.province_id,
        display_name=staff.display_name,
        expire_minutes=expire_minutes,
    )
    return StaffTokenResponse(
        access_token=token,
        expires_in=expire_minutes * 60,
        province_id=staff.province_id,
        display_name=staff.display_name,
    )
