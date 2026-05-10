"""Geo APIs: จังหวัด → อำเภอ (ตาม province) → ตำบล + รหัสไปรษณีย์ (ตาม district)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.database import get_session
from ...models.geo import District, Province, SubDistrict, SubDistrictPostcode
from ...schemas.geo import (
    DistrictRead,
    PostcodeRead,
    ProvinceRead,
    SubDistrictPostcodeLinkRead,
    SubDistrictWithPostcodesRead,
)

router = APIRouter(prefix="/v1/geo", tags=["geo"])


def _subdistrict_with_postcodes(sd: SubDistrict) -> SubDistrictWithPostcodesRead:
    links = sorted(sd.sub_district_postcodes or [], key=lambda x: x.id)
    postcodes: list[PostcodeRead] = []
    bridge_rows: list[SubDistrictPostcodeLinkRead] = []
    for link in links:
        if link.postcode is None:
            continue
        pc = PostcodeRead.model_validate(link.postcode)
        postcodes.append(pc)
        bridge_rows.append(
            SubDistrictPostcodeLinkRead(
                id=link.id,
                sub_district_id=link.sub_district_id,
                postcode_id=link.postcode_id,
                postcode=pc,
            ),
        )
    return SubDistrictWithPostcodesRead(
        id=sd.id,
        code=sd.code,
        name=sd.name,
        district_id=sd.district_id,
        postcodes=postcodes,
        sub_districts_postcode=bridge_rows,
    )


@router.get("/provinces", response_model=list[ProvinceRead])
async def list_provinces(session: AsyncSession = Depends(get_session)) -> list[ProvinceRead]:
    result = await session.execute(select(Province).order_by(Province.id))
    return [ProvinceRead.model_validate(r) for r in result.scalars().all()]


@router.get("/provinces/{province_id}", response_model=ProvinceRead)
async def get_province(
    province_id: int,
    session: AsyncSession = Depends(get_session),
) -> ProvinceRead:
    row = await session.scalar(select(Province).where(Province.id == province_id))
    if row is None:
        raise HTTPException(status_code=404, detail="province_not_found")
    return ProvinceRead.model_validate(row)


@router.get("/districts", response_model=list[DistrictRead])
async def list_districts(
    province_id: int = Query(
        ...,
        description="รหัสจังหวัด — คืนเฉพาะอำเภอใน province นี้",
    ),
    session: AsyncSession = Depends(get_session),
) -> list[DistrictRead]:
    prov = await session.scalar(select(Province).where(Province.id == province_id))
    if prov is None:
        raise HTTPException(status_code=404, detail="province_not_found")
    result = await session.execute(
        select(District).where(District.province_id == province_id).order_by(District.id),
    )
    return [DistrictRead.model_validate(r) for r in result.scalars().all()]


@router.get("/sub-districts", response_model=list[SubDistrictWithPostcodesRead])
async def list_sub_districts(
    district_id: int = Query(
        ...,
        description="รหัสอำเภอ — คืนเฉพาะตำบลใน district นี้ พร้อม postcodes และแถว sub_districts_postcode (id bridge สำหรับบันทึก)",
    ),
    session: AsyncSession = Depends(get_session),
) -> list[SubDistrictWithPostcodesRead]:
    dist = await session.scalar(select(District).where(District.id == district_id))
    if dist is None:
        raise HTTPException(status_code=404, detail="district_not_found")
    stmt = (
        select(SubDistrict)
        .where(SubDistrict.district_id == district_id)
        .options(
            selectinload(SubDistrict.sub_district_postcodes).selectinload(
                SubDistrictPostcode.postcode,
            ),
        )
        .order_by(SubDistrict.id)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_subdistrict_with_postcodes(sd) for sd in rows]
