"""Admin API — login + เปิด/ปิดบริการรายจังหวัด + สร้างเคสสุ่ม (TASK-v-care-12062026-01).

Endpoints:
  POST /v1/admin/auth/login          — username/password → admin JWT
  GET  /v1/admin/provinces           — รายการจังหวัด + สถานะเปิด/ปิด (ต้อง admin JWT)
  PUT  /v1/admin/provinces/bulk      — เปิด/ปิดทุกจังหวัดพร้อมกัน (ต้อง admin JWT)
  PUT  /v1/admin/provinces/{id}      — เปิด/ปิดรายจังหวัด (ต้อง admin JWT)
  POST /v1/admin/cases/random       — สร้างคำร้องสุ่ม (dev/staging เท่านั้น)

Auth ใช้ admin JWT (HS256, ADMIN_JWT_SECRET) แยกขาดจาก citizen token ของ ThaID.
สมัคร admin ผ่าน CLI `app.admin_cli` เท่านั้น (ไม่มี endpoint signup).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.admin_security import (
    decode_admin_jwt,
    hash_password,
    mint_admin_jwt,
    verify_password,
)
from ...core.database import get_session
from ...core.runtime import require_non_production
from ...models.admin import AdminUser, ProvinceAccessConfig
from ...models.geo import Province
from ...schemas.admin import (
    AdminLoginBody,
    AdminTokenResponse,
    ProvinceAccessBulkResult,
    ProvinceAccessRead,
    ProvinceAccessUpdate,
    RandomCaseCreatedRead,
    RandomCasesCreateBody,
    RandomCasesCreateResult,
)
from ...services.random_case import create_random_cases
from ...settings import settings

router = APIRouter(prefix="/v1/admin", tags=["admin"])

# bcrypt hash ของสตริงสุ่ม (คำนวณครั้งเดียวตอน import) — ใช้ verify เทียบเมื่อไม่พบ user
# เพื่อให้เวลาตอบสนองใกล้เคียงกรณีพบ user (ลด username enumeration ผ่าน timing)
_DUMMY_PASSWORD_HASH = hash_password("timing-equalizer-not-a-real-password")


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


async def require_admin_token(authorization: Optional[str] = Header(default=None)) -> dict:
    """Dependency: ตรวจ admin JWT จาก Authorization: Bearer <token>."""
    if not settings.admin_jwt_secret.strip():
        # ป้องกันเผลอเปิด admin API โดยไม่ตั้ง secret (จะ verify ไม่ได้)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin_jwt_secret_not_configured",
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_bearer_token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    claims = decode_admin_jwt(settings.admin_jwt_secret, token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="invalid_admin_token"
        )
    return claims


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@router.post("/auth/login", response_model=AdminTokenResponse)
async def admin_login(
    body: AdminLoginBody,
    session: AsyncSession = Depends(get_session),
) -> AdminTokenResponse:
    if not settings.admin_jwt_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin_jwt_secret_not_configured",
        )

    admin = await session.scalar(
        select(AdminUser).where(AdminUser.username == body.username.strip())
    )
    # verify เสมอ (กับ hash จริงหรือ dummy hash) ให้เวลาตอบใกล้เคียงกัน — กัน username enumeration
    hashed = admin.password_hash if admin is not None else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(body.password, hashed)
    if admin is None or not admin.is_active or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials"
        )

    expire_minutes = settings.admin_jwt_expire_minutes
    token = mint_admin_jwt(
        settings.admin_jwt_secret,
        admin_id=admin.id,
        username=admin.username,
        expire_minutes=expire_minutes,
    )
    return AdminTokenResponse(access_token=token, expires_in=expire_minutes * 60)


# ---------------------------------------------------------------------------
# Province access config
# ---------------------------------------------------------------------------


@router.get("/provinces", response_model=list[ProvinceAccessRead])
async def list_province_access(
    _claims: dict = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
) -> list[ProvinceAccessRead]:
    """รายการจังหวัดทั้งหมด + สถานะเปิด/ปิด (จังหวัดที่ไม่มี config = ปิด)."""
    rows = (
        await session.execute(
            text(
                """
                SELECT p.id, p.name,
                       COALESCE(pac.is_enabled, false) AS is_enabled,
                       pac.updated_at
                FROM province p
                LEFT JOIN province_access_config pac ON pac.province_id = p.id
                ORDER BY p.id
                """
            )
        )
    ).all()
    return [
        ProvinceAccessRead(
            province_id=r[0],
            province_name=r[1],
            is_enabled=bool(r[2]),
            updated_at=r[3],
        )
        for r in rows
    ]


# หมายเหตุลำดับ route: ต้องประกาศ "/provinces/bulk" ก่อน "/provinces/{province_id}"
# ไม่งั้น FastAPI จะ match "bulk" เป็น province_id (int) แล้ว 422
@router.put("/provinces/bulk", response_model=ProvinceAccessBulkResult)
async def update_all_province_access(
    body: ProvinceAccessUpdate,
    claims: dict = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
) -> ProvinceAccessBulkResult:
    """เปิด/ปิด *ทุกจังหวัด* พร้อมกัน — upsert province_access_config ทุกแถวใน 1 transaction."""
    admin_id_raw = claims.get("sub")
    admin_id = int(admin_id_raw) if admin_id_raw and str(admin_id_raw).isdigit() else None
    now = datetime.now(timezone.utc)

    province_ids = (await session.execute(select(Province.id))).scalars().all()
    existing = {
        cfg.province_id: cfg
        for cfg in (
            await session.execute(select(ProvinceAccessConfig))
        ).scalars().all()
    }

    for pid in province_ids:
        cfg = existing.get(pid)
        if cfg is None:
            session.add(
                ProvinceAccessConfig(
                    province_id=pid,
                    is_enabled=body.is_enabled,
                    updated_by_admin_id=admin_id,
                    updated_at=now,
                )
            )
        else:
            cfg.is_enabled = body.is_enabled
            cfg.updated_by_admin_id = admin_id
            cfg.updated_at = now

    await session.flush()
    return ProvinceAccessBulkResult(updated=len(province_ids), is_enabled=body.is_enabled)


@router.put("/provinces/{province_id}", response_model=ProvinceAccessRead)
async def update_province_access(
    province_id: int,
    body: ProvinceAccessUpdate,
    claims: dict = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
) -> ProvinceAccessRead:
    """เปิด/ปิดจังหวัด — upsert province_access_config."""
    province = await session.get(Province, province_id)
    if province is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="province_not_found"
        )

    admin_id_raw = claims.get("sub")
    admin_id = int(admin_id_raw) if admin_id_raw and str(admin_id_raw).isdigit() else None

    config = await session.scalar(
        select(ProvinceAccessConfig).where(
            ProvinceAccessConfig.province_id == province_id
        )
    )
    now = datetime.now(timezone.utc)
    if config is None:
        config = ProvinceAccessConfig(
            province_id=province_id,
            is_enabled=body.is_enabled,
            updated_by_admin_id=admin_id,
            updated_at=now,
        )
        session.add(config)
    else:
        config.is_enabled = body.is_enabled
        config.updated_by_admin_id = admin_id
        config.updated_at = now

    await session.flush()
    return ProvinceAccessRead(
        province_id=province_id,
        province_name=province.name,
        is_enabled=config.is_enabled,
        updated_at=config.updated_at,
    )


# ---------------------------------------------------------------------------
# Random cases (dev/staging)
# ---------------------------------------------------------------------------


@router.post("/cases/random", response_model=RandomCasesCreateResult)
async def admin_create_random_cases(
    body: RandomCasesCreateBody,
    _claims: dict = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
) -> RandomCasesCreateResult:
    """สร้างคำร้องสุ่ม (person + applicant + ตารางย่อย) — ใช้ทดสอบเท่านั้น ไม่ทำงานบน production."""
    try:
        require_non_production("admin_create_random_cases")
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="disabled_in_production",
        ) from exc

    if body.province_id is not None:
        province = await session.get(Province, body.province_id)
        if province is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="province_not_found"
            )

    try:
        created = await create_random_cases(
            session,
            count=body.count,
            province_id=body.province_id,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail.startswith("missing_lookup_data"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail
            ) from exc
        if detail == "no_postcode_for_province":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=detail
            ) from exc
        if detail == "no_postcode_data":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=detail
        ) from exc

    return RandomCasesCreateResult(
        created=len(created),
        cases=[
            RandomCaseCreatedRead(
                applicant_id=c.applicant_id,
                case_number=c.case_number,
                persons_id=c.persons_id,
                cid=c.cid,
                full_name=c.full_name,
                province_id=c.province_id,
                province_name=c.province_name,
            )
            for c in created
        ],
    )
