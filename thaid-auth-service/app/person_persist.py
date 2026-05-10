"""บันทึกข้อมูลผู้ใช้จาก ThaiD ลง `persons` — ถ้ามี cid แล้วไม่ insert / ไม่ update."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from . import ThaID
from . import db

logger = logging.getLogger(__name__)


def _parse_birth_date(raw: str) -> Optional[date]:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return None


def _normalize_cid(pid: str) -> Optional[str]:
    """รับ pid/sub จาก ThaiD — ตัดอักขระที่ไม่ใช่ตัวเลขแล้วต้องได้ 13 หลัก (เลขบัตรประชาชน)."""
    p = re.sub(r"\D", "", (pid or "").strip())
    if len(p) == 13:
        return p
    return None


async def _resolve_sub_district_postcode_id(
    session: AsyncSession,
    formatted_address: str,
    extra_postcode: str,
) -> Optional[int]:
    """
    หา id ของแถว `sub_districts_postcode` จากชื่อตำบล + รหัสไปรษณีย์ (และ อ./จ. ถ้ามี)
    ลำดับ: (ต+รหัส+อ+จ) → (ต+รหัส+อ) → (ต+รหัส) → (ต+อ+จ เมื่อไม่มีรหัสในข้อความ)
    """
    parts = ThaID.parse_thai_address_geo(formatted_address)
    sub = (parts.get("subdistrict") or "").strip()
    if not sub:
        return None

    dist = (parts.get("district") or "").strip() or None
    prov = (parts.get("province") or "").strip() or None
    pc = (parts.get("postcode") or "").strip()
    if len(pc) != 5 and extra_postcode:
        ep = re.sub(r"\D", "", (extra_postcode or "").strip())
        if len(ep) == 5:
            pc = ep
    pc_ok = len(pc) == 5

    if pc_ok and dist and prov:
        r = await session.execute(
            text(
                """
                SELECT sdp.id
                FROM sub_districts_postcode sdp
                INNER JOIN sub_districts sd ON sd.id = sdp.sub_district_id
                INNER JOIN districts d ON d.id = sd.district_id
                INNER JOIN province p ON p.id = d.province_id
                INNER JOIN postcode pc ON pc.id = sdp.postcode_id
                WHERE TRIM(sd.name) = :sub
                  AND TRIM(pc.name) = :pc
                  AND TRIM(d.name) = :dist
                  AND TRIM(p.name) = :prov
                ORDER BY sdp.id
                LIMIT 1
                """
            ),
            {"sub": sub, "pc": pc, "dist": dist, "prov": prov},
        )
        row = r.first()
        if row:
            return int(row[0])

    if pc_ok and dist:
        r = await session.execute(
            text(
                """
                SELECT sdp.id
                FROM sub_districts_postcode sdp
                INNER JOIN sub_districts sd ON sd.id = sdp.sub_district_id
                INNER JOIN districts d ON d.id = sd.district_id
                INNER JOIN postcode pc ON pc.id = sdp.postcode_id
                WHERE TRIM(sd.name) = :sub
                  AND TRIM(pc.name) = :pc
                  AND TRIM(d.name) = :dist
                ORDER BY sdp.id
                LIMIT 1
                """
            ),
            {"sub": sub, "pc": pc, "dist": dist},
        )
        row = r.first()
        if row:
            return int(row[0])

    if pc_ok:
        r = await session.execute(
            text(
                """
                SELECT sdp.id
                FROM sub_districts_postcode sdp
                INNER JOIN sub_districts sd ON sd.id = sdp.sub_district_id
                INNER JOIN postcode pc ON pc.id = sdp.postcode_id
                WHERE TRIM(sd.name) = :sub
                  AND TRIM(pc.name) = :pc
                ORDER BY sdp.id
                LIMIT 1
                """
            ),
            {"sub": sub, "pc": pc},
        )
        row = r.first()
        if row:
            return int(row[0])

    if dist and prov:
        r = await session.execute(
            text(
                """
                SELECT sdp.id
                FROM sub_districts_postcode sdp
                INNER JOIN sub_districts sd ON sd.id = sdp.sub_district_id
                INNER JOIN districts d ON d.id = sd.district_id
                INNER JOIN province p ON p.id = d.province_id
                WHERE TRIM(sd.name) = :sub
                  AND TRIM(d.name) = :dist
                  AND TRIM(p.name) = :prov
                ORDER BY sdp.id
                LIMIT 1
                """
            ),
            {"sub": sub, "dist": dist, "prov": prov},
        )
        row = r.first()
        if row:
            return int(row[0])

    logger.info(
        "sub_district_postcode_lookup: no row (sub=%r dist=%r prov=%r pc=%r)",
        sub,
        dist,
        prov,
        pc if pc_ok else None,
    )
    return None


async def _resolve_prefix_id(session: AsyncSession, title_th: str) -> int:
    t = (title_th or "").strip()
    if not t:
        return 1
    r = await session.execute(
        text("SELECT id FROM prefix_type WHERE TRIM(name) = :name LIMIT 1"),
        {"name": t},
    )
    row = r.first()
    if row:
        return int(row[0])
    return 1


async def persist_new_person_if_absent(profile: Dict[str, str]) -> None:
    """
    ถ้ามี engine/session factory และข้อมูลครบตามที่ตาราง persons บังคับ และยังไม่มีแถว cid นี้ — insert แถวเดียว
    """
    if db.SessionLocal is None:
        return

    cid = _normalize_cid(profile.get("pid") or "")
    if not cid:
        raw = (profile.get("pid") or "").strip()
        if raw:
            digits = re.sub(r"\D", "", raw)
            logger.warning(
                "person_persist_skip: pid/sub is not 13 digits (got %s digit chars); table=persons",
                len(digits),
            )
        return

    fn = (profile.get("given_name") or "").strip()
    ln = (profile.get("family_name") or "").strip()
    if not fn or not ln:
        logger.info("person_persist_skip: missing given_name or family_name for cid=%s", cid[:4] + "********")
        return

    bd = _parse_birth_date(profile.get("birthdate") or "")
    if bd is None:
        logger.info("person_persist_skip: missing or invalid birthdate for cid=%s", cid[:4] + "********")
        return

    adr_house_num, adr_moo = ThaID.parse_dopa_formatted_address(profile.get("address") or "")
    gender = (profile.get("gender") or "").strip() or None

    async with db.SessionLocal() as session:
        exists = await session.execute(text("SELECT 1 FROM persons WHERE cid = :cid LIMIT 1"), {"cid": cid})
        if exists.scalar() is not None:
            logger.info("person_persist_skip: row already exists for cid prefix=%s***", cid[:3])
            return

        prefix_id = await _resolve_prefix_id(session, profile.get("title_th") or "")

        sdp_id = await _resolve_sub_district_postcode_id(
            session,
            profile.get("address") or "",
            profile.get("address_postcode") or "",
        )

        await session.execute(
            text(
                """
                INSERT INTO persons (
                    prefix_id, first_name, last_name, cid, birth_date,
                    sub_district_postcode_id, gender, adr_moo, adr_house_num
                ) VALUES (
                    :prefix_id, :first_name, :last_name, :cid, :birth_date,
                    :sdp_id, :gender, :adr_moo, :adr_house_num
                )
                """
            ),
            {
                "prefix_id": prefix_id,
                "first_name": fn,
                "last_name": ln,
                "cid": cid,
                "birth_date": bd,
                "sdp_id": sdp_id,
                "gender": gender,
                "adr_moo": adr_moo,
                "adr_house_num": adr_house_num,
            },
        )
        await session.commit()
        logger.info("person_persist_ok: inserted persons row for cid prefix=%s***", cid[:3])
