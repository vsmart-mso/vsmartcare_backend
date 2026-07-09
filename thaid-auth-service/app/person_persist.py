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
    # กรณี ThaiD ส่ง birthdate ไม่ครบ เช่น
    #   "2487"         → ไม่ส่งเดือน/วัน → 1 ม.ค. ของปีที่ส่ง (แปลง พ.ศ. ≥2400 เป็น ค.ศ.)
    #   "2487-00-00"   → เช่นเดียวกับปีอย่างเดียว
    #   "2487-05-00"   → มีเดือน ไม่มีวัน → วันที่ 1 ของเดือนนั้น
    m = re.match(r"^(\d{4})(?:[-/](\d{1,2})(?:[-/](\d{1,2}))?)?", raw)
    if m:
        try:
            year = int(m.group(1))
            if year >= 2400:
                year -= 543

            def _sent_part(value: str | None) -> int | None:
                if value is None or value == "":
                    return None
                n = int(value)
                return n if n > 0 else None

            month_sent = _sent_part(m.group(2))
            day_sent = _sent_part(m.group(3))
            if month_sent is None and day_sent is None:
                month, day = 1, 1
            elif month_sent is not None and day_sent is None:
                month, day = month_sent, 1
            elif month_sent is None and day_sent is not None:
                month, day = 1, day_sent
            else:
                month, day = month_sent, day_sent
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


# ชื่อจังหวัดที่ ThaiD/DOPA อาจเขียนต่างจากชื่อทางการในตาราง `province` (พบจริง: กรุงเทพฯ)
_PROVINCE_NAME_ALIASES: dict[str, list[str]] = {
    "กรุงเทพมหานคร": ["กรุงเทพ", "กทม"],
}


def _match_province_id(formatted_address: str, province_rows: list[tuple[int, str]]) -> Optional[int]:
    """หา province.id โดยไล่หาว่าชื่อจังหวัดใน 77 จังหวัด (+ alias) ตัวไหนปรากฏใน address
    ที่ตำแหน่ง "ขวาสุด" (ที่อยู่แบบ DOPA จบด้วยชื่อจังหวัดแล้วตามด้วยรหัสไปรษณีย์เสมอ)

    ต่างจาก _resolve_sub_district_postcode_id ตรงที่ไม่พึ่งตำแหน่ง ต./อ./จ. เลย จึงไม่พังกับ
    ที่อยู่กรุงเทพฯ (แขวง/เขต ไม่มี "จ." นำหน้า) หรือเขตปกครองพิเศษอย่างเมืองพัทยา
    (ไม่ใช่ "อำเภอ" จึงไม่มีคำว่า "อ." นำหน้า ทำให้การตัดคำแบบเดิมหาอำเภอไม่เจอ)
    และไม่ต้องพึ่ง sub_districts_postcode ตรงเป๊ะทุกตัวอักษรแบบ resolve เดิม
    """
    text_addr = (formatted_address or "").strip()
    if not text_addr:
        return None

    best_id: Optional[int] = None
    best_pos = -1
    for pid, name in province_rows:
        real_name = (name or "").strip()
        if not real_name:
            continue
        for candidate in (real_name, *_PROVINCE_NAME_ALIASES.get(real_name, [])):
            pos = text_addr.rfind(candidate)
            if pos > best_pos:
                best_pos = pos
                best_id = int(pid)
    return best_id


async def _fetch_province_rows(session: AsyncSession) -> list[tuple[int, str]]:
    rows = (await session.execute(text("SELECT id, name FROM province"))).all()
    return [(int(r[0]), str(r[1])) for r in rows]


async def resolve_province_id_from_address(
    session: AsyncSession,
    formatted_address: str,
) -> Optional[int]:
    """จุดคำนวณจังหวัดจุดเดียวในระบบ (TASK-v-care-12062026-01) — ใช้ตอน login (เก็บ persons.province_id)
    และตอน backfill แถวเก่า เพื่อให้ submit gate ฝั่ง case-service
    (services/province_access.py::is_province_enabled_by_person_id) อ่านค่าที่คำนวณจากวิธีเดียวกันเป๊ะ
    """
    rows = await _fetch_province_rows(session)
    return _match_province_id(formatted_address, rows)


async def resolve_province_id_from_address_standalone(formatted_address: str) -> Optional[int]:
    """เหมือน resolve_province_id_from_address แต่เปิด session เอง — ใช้ตอน login-check ก่อน persist

    fail-open เมื่อ DB error (เช่น connection blip) — เหมือน get_province_access_status_by_id
    ข้างล่าง ไม่งั้น login จะ 500 ทั้งที่ควรจะปล่อยผ่านแบบ fail-open
    """
    if db.SessionLocal is None:
        return None
    try:
        async with db.SessionLocal() as session:
            return await resolve_province_id_from_address(session, formatted_address)
    except Exception:  # noqa: BLE001 — fail open ไม่บล็อกการ login เพราะ DB มีปัญหาชั่วคราว
        logger.exception("province_resolve_failed (fail open)")
        return None


async def get_province_access_status_by_id(province_id: Optional[int]) -> bool:
    """True = จังหวัดเปิดรับบันทึกข้อมูล (TASK-v-care-12062026-01) — อ่าน province_access_config
    ด้วย province_id เดียวกับที่ case-service ใช้ตอน submit

    - province_id=None (resolve จากที่อยู่ไม่ได้ เช่น ที่อยู่ว่าง/mock) → True (fail-open ไม่บล็อก)
    - ไม่มี DB (`SessionLocal is None`) → True (backward compat — dev ที่ไม่ตั้ง DATABASE_URL)
    - ไม่มี config แถวนั้น → False (default deny)
    """
    if db.SessionLocal is None or province_id is None:
        return True
    try:
        async with db.SessionLocal() as session:
            r = await session.execute(
                text("SELECT is_enabled FROM province_access_config WHERE province_id = :pid LIMIT 1"),
                {"pid": province_id},
            )
            row = r.first()
            return bool(row[0]) if row else False
    except Exception:  # noqa: BLE001 — เช่น ตารางยังไม่ถูก migrate → fail open ไม่บล็อกการ login
        logger.exception("province_access_check_failed (fail open): province_id=%s", province_id)
        return True


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
    address_raw = profile.get("address") or ""

    async with db.SessionLocal() as session:
        exists = await session.execute(
            text("SELECT id, province_id FROM persons WHERE cid = :cid LIMIT 1"), {"cid": cid}
        )
        existing_row = exists.first()
        if existing_row is not None:
            existing_id, existing_province_id = existing_row
            logger.info("person_persist_skip: row already exists for cid prefix=%s***", cid[:3])
            # Backfill province_id ให้แถวเก่าที่ resolve ไม่เคยสำเร็จ (TASK-v-care-12062026-01) —
            # resolve เดิม (sub_district_postcode_id) พังกับที่อยู่กรุงเทพฯ/เมืองพัทยา ฯลฯ ทำให้ค้าง NULL
            # ตลอดกาล ส่วน province_id ใช้ _match_province_id ที่ทนกว่า จึงลองซ่อมใหม่ทุกครั้งที่ login
            if existing_province_id is None:
                resolved_province_id = await resolve_province_id_from_address(session, address_raw)
                if resolved_province_id is not None:
                    await session.execute(
                        text("UPDATE persons SET province_id = :pid WHERE id = :id"),
                        {"pid": resolved_province_id, "id": existing_id},
                    )
                    await session.commit()
                    logger.info(
                        "person_persist_backfill: province_id=%s set for cid prefix=%s***",
                        resolved_province_id,
                        cid[:3],
                    )
            return

        title_for_prefix = (profile.get("title_th") or "").strip()
        if not title_for_prefix:
            title_for_prefix, _ = _extract_title_from_given_name(fn)
        prefix_id = await _resolve_prefix_id(session, title_for_prefix)

        sdp_id = await _resolve_sub_district_postcode_id(
            session,
            address_raw,
            profile.get("address_postcode") or "",
        )
        province_id = await resolve_province_id_from_address(session, address_raw)

        await session.execute(
            text(
                """
                INSERT INTO persons (
                    prefix_id, first_name, last_name, cid, birth_date,
                    sub_district_postcode_id, province_id, gender, adr_moo, adr_house_num
                ) VALUES (
                    :prefix_id, :first_name, :last_name, :cid, :birth_date,
                    :sdp_id, :province_id, :gender, :adr_moo, :adr_house_num
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
                "province_id": province_id,
                "gender": gender,
                "adr_moo": adr_moo,
                "adr_house_num": adr_house_num,
            },
        )
        await session.commit()
        logger.info("person_persist_ok: inserted persons row for cid prefix=%s***", cid[:3])
