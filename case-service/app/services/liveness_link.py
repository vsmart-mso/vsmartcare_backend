"""ผูกผลยืนยันตัวตนเข้ากับคำร้อง ตอน POST /v1/cases.

ค่าคงที่ที่ฟังก์ชันนี้รักษาไว้: **ทุก applicant มีแถวใน `liveness_attempts` อย่างน้อย 1 แถวเสมอ**
ทำให้ query "คำร้องที่ไม่มีแถว" กลายเป็นสัญญาณผิดปกติที่ต้องไปสืบ แทนที่จะเป็นเรื่องปกติ
ที่ตีความไม่ได้ว่าเป็นระบบล่ม / มีคนหลบ / ยื่นก่อนมีฟีเจอร์นี้

แถว `NO_ATTEMPT` ถูกเขียนโดยเซิร์ฟเวอร์ ณ จุดที่ผู้ใช้เลี่ยงไม่ได้ (ต้องยิง POST /v1/cases
ถึงจะได้คำร้อง) คนที่ข้ามด่านนี้จึงทิ้งร่องรอยที่ลบไม่ได้ — ต่างจากการให้ frontend
เป็นคนรายงานว่าข้าม ซึ่งแค่ "ไม่เรียก" ก็หายไปเฉย ๆ

⚠️ กันได้แค่ "ข้ามแบบเงียบ ๆ" ไม่ได้กันการปลอมผลว่า completed
เรื่องนั้นต้องรอ verify signature ฝั่งเซิร์ฟเวอร์
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.liveness_attempt import (
    SKIP_NO_ATTEMPT,
    SKIP_REPLAYED,
    STATUS_SKIPPED,
    LivenessAttempt,
)

logger = logging.getLogger("case-service.liveness")


def _server_marked_row(persons_id: int, applicant_id: int, skip_reason: str) -> LivenessAttempt:
    """แถวที่เซิร์ฟเวอร์เขียนเอง — reference_id สร้างใหม่เพราะคอลัมน์เป็น NOT NULL UNIQUE"""
    return LivenessAttempt(
        persons_id=persons_id,
        applicant_id=applicant_id,
        reference_id=str(uuid.uuid4()),
        status=STATUS_SKIPPED,
        skip_reason=skip_reason,
    )


async def link_liveness_to_applicant(
    session: AsyncSession,
    *,
    applicant_id: int,
    persons_id: int,
    reference_id: str | None,
) -> None:
    """ผูก attempt เข้ากับคำร้อง หรือบันทึกว่าไม่มี — **ต้องไม่ทำให้การสร้างคำร้องล้มเหลว**

    ครอบด้วย SAVEPOINT เพราะ INSERT ที่นี่ชน UNIQUE ได้ ถ้าไม่มี savepoint
    IntegrityError จะทำให้ทรานแซกชันทั้งก้อนเป็นพิษ แล้วคำร้องที่สร้างไว้แล้วหายไปด้วย
    การ try/except เฉย ๆ ไม่พอ
    """
    try:
        async with session.begin_nested():
            await _link(
                session,
                applicant_id=applicant_id,
                persons_id=persons_id,
                reference_id=reference_id,
            )
    except Exception:  # noqa: BLE001 — ตั้งใจกลืนทุกอย่าง คำร้องสำคัญกว่าสถิติ
        logger.exception(
            "ผูก liveness กับคำร้องไม่สำเร็จ applicant_id=%s reference_id=%s "
            "— ปล่อยให้คำร้องถูกสร้างต่อ",
            applicant_id,
            reference_id,
        )


async def _link(
    session: AsyncSession,
    *,
    applicant_id: int,
    persons_id: int,
    reference_id: str | None,
) -> None:
    if not reference_id:
        session.add(_server_marked_row(persons_id, applicant_id, SKIP_NO_ATTEMPT))
        await session.flush()
        return

    row = await session.scalar(
        select(LivenessAttempt).where(LivenessAttempt.reference_id == reference_id)
    )

    if row is None or row.persons_id != persons_id:
        # อ้างถึง attempt ที่ไม่มีอยู่จริง หรือของคนอื่น — เชื่อไม่ได้ ถือว่าไม่มีการสแกน
        logger.warning(
            "reference_id ที่ยื่นมาไม่ถูกต้อง applicant_id=%s persons_id=%s reference_id=%s "
            "(%s) — บันทึกเป็น %s",
            applicant_id,
            persons_id,
            reference_id,
            "ไม่พบแถว" if row is None else "เป็นของ person อื่น",
            SKIP_NO_ATTEMPT,
        )
        session.add(_server_marked_row(persons_id, applicant_id, SKIP_NO_ATTEMPT))
        await session.flush()
        return

    if row.applicant_id is not None:
        # เอาการสแกนครั้งเดียวไปยื่นหลายคำร้อง — ไม่บล็อกตามข้อตกลงรอบนี้
        # แต่ไม่แก้แถวเดิม (จะทำให้สถิติของคำร้องแรกเพี้ยน) และทิ้งหลักฐานไว้
        logger.warning(
            "reference_id ถูกใช้ไปแล้วกับ applicant_id=%s แต่ถูกยื่นซ้ำกับ applicant_id=%s "
            "reference_id=%s — บันทึกเป็น %s",
            row.applicant_id,
            applicant_id,
            reference_id,
            SKIP_REPLAYED,
        )
        session.add(_server_marked_row(persons_id, applicant_id, SKIP_REPLAYED))
        await session.flush()
        return

    row.applicant_id = applicant_id
    await session.flush()
