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
    # กรณีผู้สูงอายุที่ ThaID ส่ง birthdate ไม่ครบ เช่น
    #   "1952"         → date(1952, 1, 1)
    #   "1952-00-00"   → date(1952, 1, 1)   (เดือน/วัน = 0)
    #   "1952-05-00"   → date(1952, 5, 1)   (มีเดือน แต่ไม่มีวัน)
    # ส่วนที่ขาดหาย/เป็น 0 ให้ default เป็น 1
    m = re.match(r'^(\d{4})(?:[-/](\d{1,2})(?:[-/](\d{1,2}))?)?', raw)
    if m:
        try:
            year  = int(m.group(1))
            month = int(m.group(2) or 0) or 1
            day   = int(m.group(3) or 0) or 1
            return date(year, month, day)
        except ValueError:
            return None
    return None


def _normalize_cid(pid: str) -> Optional[str]:
    """รับ pid/sub จาก ThaiD — ตัดอักขระที่ไม่ใช่ตัวเลขแล้วต้องได้ 13 หลัก (เลขบัตรประชาชน)."""
    p = re.sub(r"\D", "", (pid or "").strip())
    if len(p) == 13:
        return p
    return None


async def get_province_access_status(province_name: str) -> bool:
    """True = จังหวัดเปิดรับบันทึกข้อมูล (TASK-v-care-12062026-01).

    อ่าน `province_access_config` (ตารางเดียวกับ case-service DB).
    - ไม่มี config / is_enabled=false → ปิด (default deny)
    - ไม่มี DB (`SessionLocal is None`) → True (backward compat — dev ที่ไม่ตั้ง DATABASE_URL)
    """
    if db.SessionLocal is None:
        return True
    name = (province_name or "").strip()
    if not name:
        return True  # parse ไม่ได้จังหวัด (เช่น mock/address ว่าง) → ไม่ block
    try:
        async with db.SessionLocal() as session:
            r = await session.execute(
                text(
                    """
                    SELECT pac.is_enabled
                    FROM province_access_config pac
                    INNER JOIN province p ON p.id = pac.province_id
                    WHERE TRIM(p.name) = :name
                    LIMIT 1
                    """
                ),
                {"name": name},
            )
            row = r.first()
            return bool(row[0]) if row else False
    except Exception:  # noqa: BLE001 — เช่น ตารางยังไม่ถูก migrate → fail open ไม่บล็อกการ login
        logger.exception("province_access_check_failed (fail open): province=%s", name)
        return True


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


# รหัส/ชื่อย่อจาก ThaiD → ชื่อใน master `prefix_type` (seed: นาย/นาง/นางสาว)
_PREFIX_ALIASES: dict[str, str] = {
    "1": "นาย",
    "2": "นาง",
    "3": "นางสาว",
    "น.ส.": "นางสาว",
    "น.ส": "นางสาว",
    "น.": "นาย",
    "น": "นาย",
    "นาย": "นาย",
    "นาง": "นาง",
    "นางสาว": "นางสาว",
}

_PREFIX_ORDER_FOR_NAME = ("นางสาว", "นาง", "นาย")


def _canonical_prefix_label(title_th: str) -> str:
    t = (title_th or "").strip()
    if not t:
        return ""
    return _PREFIX_ALIASES.get(t, t)


def _extract_title_from_given_name(given_name: str) -> tuple[str, str]:
    """กรณี ThaiD ไม่ส่ง title แต่รวมคำนำหน้าไว้ใน given_name."""
    gn = (given_name or "").strip()
    for prefix in _PREFIX_ORDER_FOR_NAME:
        if gn.startswith(prefix + " "):
            return prefix, gn[len(prefix) + 1 :].strip()
    return "", gn


async def _resolve_prefix_id(session: AsyncSession, title_th: str) -> int:
    canonical = _canonical_prefix_label(title_th)
    if not canonical:
        logger.warning("prefix_resolve: empty title, defaulting prefix_id=1")
        return 1
    r = await session.execute(
        text("SELECT id FROM prefix_type WHERE TRIM(name) = :name LIMIT 1"),
        {"name": canonical},
    )
    row = r.first()
    if row:
        return int(row[0])
    logger.warning(
        "prefix_resolve: no prefix_type match for title_th=%r (canonical=%r), defaulting prefix_id=1",
        title_th,
        canonical,
    )
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

        title_for_prefix = (profile.get("title_th") or "").strip()
        if not title_for_prefix:
            title_for_prefix, _ = _extract_title_from_given_name(fn)
        prefix_id = await _resolve_prefix_id(session, title_for_prefix)

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
